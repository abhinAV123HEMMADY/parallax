"""Creates a Topic for a video that matches nothing in the graph.

`topic_match.py` deliberately returns None below its confidence thresholds, because attributing
a note to the wrong concept corrupts the mastery graph and propagates into the struggle feed.
That is the right call when the graph is the authority on what exists. It stops being the right
call once the learner is watching arbitrary YouTube — then "no confident match" almost always
means *the graph has never heard of this subject*, not *this note is unattributable*, and an
unmapped note silently loses flashcards, struggle signals and the peer layer.

So this module handles the second case only: it runs after both matchers decline, and mints a
topic rather than guessing among topics that were never plausible. The distinction is preserved
in the data — an auto-created topic carries no prerequisite edges and no misconceptions, so it
can hold notes and flashcards without pretending to a place in the curriculum it hasn't earned.

Naming uses the model when a key is set and a deterministic fallback when it isn't, matching
every other LLM-backed node here. The fallback is not a placeholder: with no key configured it
is the only path that ever runs, so it has to produce a name a learner would recognise.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from parallax_embed import embed_document, embed_query

from app.llm import forced_tool_call
from app.models import Topic, VideoNote

from .topic_match import _NOISE, _tokens

# Cosine similarity above which a freshly proposed name is treated as a topic that already
# exists rather than a new one. Deliberately well above the 0.62 *match* threshold: that one
# asks "is this video about this topic", which tolerates looseness because a human sees the
# result. This one asks "are these two labels the same concept", and a false positive here
# permanently merges two subjects, so it demands near-synonymy.
NEAR_DUPLICATE_THRESHOLD = 0.88

# Longest name worth keeping. A topic is a label on a graph node, not a sentence; past about
# four words it stops being something the Mastery Map can render or a learner can scan.
_MAX_NAME_WORDS = 4

# Packaging words that survive topic_match's noise list because they are harmless *there* —
# that list only has to stop two topic names colliding, and no topic is called "understanding".
# Here they are actively wrong: they are exactly the words a lecture title wraps the concept in,
# so leaving them produces "understanding electron configuration" instead of the concept itself.
_TITLE_FILLER = {
    "understanding", "understand", "learn", "learning", "guide", "crash", "review", "overview",
    "chapter", "unit", "week", "day", "class", "episode", "session", "series", "complete",
    "beginners", "beginner", "advanced", "simple", "simply", "easy", "quick", "made", "step",
    "steps", "everything", "need", "know", "explain", "explaining", "revision", "revise",
    "summary", "summarised", "summarized", "problems", "practice", "solved", "solving",
    "from", "scratch", "using", "into", "your", "you", "this", "that", "solve",
}

# Field labels. A title carries these as the *course* name ("Crash Course Biology"), so they
# describe the shelf rather than the concept. Dropped only when something else survives — for a
# video genuinely called "Biology Basics" the label is all there is, and is better than nothing.
_SUBJECT_WORDS = {
    "math", "maths", "mathematics", "physics", "chemistry", "biology", "history", "economics",
    "calculus", "algebra", "science", "statistics", "programming",
}

# Coarse subject buckets. Only used to populate Topic.subject, which is a display and grouping
# field — nothing routes on it, so a wrong bucket is cosmetic rather than structural.
_SUBJECT_HINTS: list[tuple[str, set[str]]] = [
    ("math", {"algebra", "calculus", "derivative", "derivatives", "integral", "integration",
              "limit", "limits", "matrix", "vector", "theorem", "equation", "geometry",
              "trigonometry", "probability", "statistics", "logarithm", "polynomial"}),
    ("physics", {"force", "momentum", "velocity", "acceleration", "quantum", "relativity",
                 "thermodynamics", "entropy", "voltage", "circuit", "magnetic", "gravity",
                 "wave", "particle", "electron"}),
    ("chemistry", {"atom", "molecule", "bond", "reaction", "acid", "base", "oxidation",
                   "stoichiometry", "orbital", "isotope", "compound", "titration", "enthalpy"}),
    ("biology", {"cell", "dna", "rna", "protein", "enzyme", "mitosis", "meiosis", "genetics",
                 "evolution", "photosynthesis", "neuron", "chromosome", "bacteria"}),
    ("computer science", {"algorithm", "recursion", "pointer", "compiler", "database", "binary",
                          "sorting", "hashing", "complexity", "runtime", "stack", "queue",
                          "graph", "programming", "python", "javascript", "memory"}),
    ("history", {"revolution", "empire", "treaty", "dynasty", "civilization", "colonial",
                 "medieval", "renaissance", "century", "war"}),
    ("economics", {"inflation", "supply", "demand", "market", "elasticity", "monopoly", "gdp",
                   "fiscal", "monetary", "equilibrium"}),
]

_NAME_TOOL = {
    "name": "name_topic",
    "description": "Name the single academic concept a lecture teaches.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "The concept in 1-4 words, lowercase, as it would title a textbook section. "
                    "Name the concept, not the video: 'integration by parts', not "
                    "'Calculus 2 Lecture 7'."
                ),
            },
            "subject": {
                "type": "string",
                "description": "Broad field, e.g. math, physics, chemistry, biology, history.",
            },
        },
        "required": ["name", "subject"],
    },
}


@dataclass
class ProposedTopic:
    """A topic that would be created. Returned without writing, so a GET can preview it."""

    name: str
    subject: str
    slug: str


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _infer_subject(tokens: set[str]) -> str:
    for subject, hints in _SUBJECT_HINTS:
        if tokens & hints:
            return subject
    return "general"


def _salient_terms(video_title: str, transcript: str) -> list[str]:
    """The title's content words, in title order, keeping only what the transcript dwells on.

    The title says what the video is called; the transcript says what it actually spends its
    time on. Frequency decides *which* words survive — in "Lecture 7: Understanding Electron
    Configuration", only the ones the lecturer repeats are the concept — but the surviving words
    are emitted in the order the title wrote them. Ranking by frequency scrambles that into
    "revolution french", which is not a name anyone would recognise.
    """
    title_tokens = [
        w for w in re.split(r"[^a-z0-9]+", video_title.lower())
        # Pure digits are episode numbers, years and course codes — never the concept.
        if w and not w.isdigit() and w not in _NOISE and w not in _TITLE_FILLER and len(w) > 2
    ]
    # dict.fromkeys de-duplicates while preserving first-seen order.
    title_tokens = list(dict.fromkeys(title_tokens))

    # Drop the field label only if a concept survives it; otherwise the label *is* the concept.
    without_subject = [w for w in title_tokens if w not in _SUBJECT_WORDS]
    if without_subject:
        title_tokens = without_subject

    if not title_tokens:
        return []
    if len(title_tokens) <= _MAX_NAME_WORDS:
        return title_tokens

    body = re.split(r"[^a-z0-9]+", transcript.lower())
    counts: dict[str, int] = {}
    for word in body:
        if word in title_tokens:
            counts[word] = counts.get(word, 0) + 1

    # Select by frequency (title order breaks ties), then restore title order for the name.
    keep = set(
        sorted(title_tokens, key=lambda w: (-counts.get(w, 0), title_tokens.index(w)))[
            :_MAX_NAME_WORDS
        ]
    )
    return [w for w in title_tokens if w in keep]


def propose_from_text(video_title: str, transcript: str) -> ProposedTopic:
    """Deterministic naming. The only path that runs when no API key is configured."""
    terms = _salient_terms(video_title, transcript)

    if terms:
        name = " ".join(terms[:_MAX_NAME_WORDS])
    else:
        # Nothing usable in the title — fall back to the title verbatim, trimmed. Better a
        # clumsy topic the learner recognises than a note filed under nothing.
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", video_title).strip()
        name = " ".join(cleaned.split()[:_MAX_NAME_WORDS]).lower() or "untitled video"

    subject = _infer_subject(_tokens(video_title) | _tokens(transcript[:2000]))
    return ProposedTopic(name=name, subject=subject, slug=slugify(name))


async def propose_topic(video_title: str, transcript: str) -> ProposedTopic:
    """Best available name for the concept a video teaches. Never raises."""
    result = await forced_tool_call(
        system=(
            "You label educational videos with the single academic concept they teach, for a "
            "learning app's topic graph. Prefer the standard textbook term over the video's "
            "own phrasing."
        ),
        content=f"Title: {video_title}\n\nTranscript excerpt:\n{transcript[:3000]}",
        tool=_NAME_TOOL,
        max_tokens=200,
    )

    if not result or not str(result.get("name", "")).strip():
        return propose_from_text(video_title, transcript)

    name = " ".join(str(result["name"]).lower().split()[:_MAX_NAME_WORDS])
    subject = str(result.get("subject") or "general").lower().strip() or "general"
    slug = slugify(name)
    if not slug:
        return propose_from_text(video_title, transcript)
    return ProposedTopic(name=name, subject=subject, slug=slug)


async def find_equivalent(db: AsyncSession, proposal: ProposedTopic) -> Topic | None:
    """An existing topic the proposal is just another name for, or None.

    Checked in two passes because they fail differently. The slug pass catches the same words
    and is exact. The embedding pass catches 'electron configuration' proposed when 'electron
    orbitals' already exists — which the slug pass cannot see, and which would otherwise split
    one concept across two nodes and halve the evidence behind both.
    """
    exact = await db.get(Topic, proposal.slug)
    if exact is not None:
        return exact

    by_name = (
        await db.execute(select(Topic).where(Topic.name == proposal.name).limit(1))
    ).scalars().first()
    if by_name is not None:
        return by_name

    vector = embed_query(proposal.name)
    row = (
        await db.execute(
            select(Topic, (1 - Topic.content_embedding.cosine_distance(vector)).label("score"))
            .where(Topic.content_embedding.isnot(None))
            .order_by(Topic.content_embedding.cosine_distance(vector))
            .limit(1)
        )
    ).first()
    if row is None:
        return None

    topic, score = row
    return topic if float(score) >= NEAR_DUPLICATE_THRESHOLD else None


async def topic_of_existing_note(db: AsyncSession, video_id: str) -> str | None:
    """The topic an earlier note on this same video was filed under, if any."""
    return (
        await db.execute(
            select(VideoNote.topic_id)
            .where(VideoNote.video_id == video_id, VideoNote.topic_id.isnot(None))
            .order_by(VideoNote.created_at)
            .limit(1)
        )
    ).scalars().first()


async def ensure_topic(
    db: AsyncSession, video_title: str, transcript: str, video_id: str | None = None
) -> tuple[str, bool]:
    """Returns (topic_id, created). Reuses an equivalent topic when one exists.

    Does not commit — the calling route owns the transaction, matching the rest of this package.
    """
    # One video is one concept, so a second note on it must land on the first note's topic —
    # exactly, not by similarity. Naming is not stable enough to rely on otherwise: the model
    # names a video "pointers and memory allocation", then a rate limit sends the next call to
    # the deterministic fallback, which names the same video "cs50 memory". Those are far
    # enough apart to clear the near-duplicate threshold and would fork one video into two
    # topics, splitting its notes. This check makes that impossible rather than unlikely.
    if video_id:
        existing_id = await topic_of_existing_note(db, video_id)
        if existing_id is not None:
            return existing_id, False

    proposal = await propose_topic(video_title, transcript)

    existing = await find_equivalent(db, proposal)
    if existing is not None:
        return existing.id, False

    # A slug collision here means the id is taken by a topic that is *not* equivalent (the
    # checks above would have returned it), so the new one needs a distinct id.
    topic_id = proposal.slug
    if await db.get(Topic, topic_id) is not None:
        suffix = 2
        while await db.get(Topic, f"{topic_id}-{suffix}") is not None:
            suffix += 1
        topic_id = f"{topic_id}-{suffix}"

    topic = Topic(
        id=topic_id,
        name=proposal.name,
        subject=proposal.subject,
        content_embedding=embed_document(proposal.name),
        # No prerequisite edges and no misconceptions: this concept was discovered from a video,
        # not authored into the curriculum. It can hold notes, flashcards and mastery; it stays
        # out of gap redirection and Protégé Mode until someone places it in the graph.
        common_misconceptions=None,
    )
    db.add(topic)
    await db.flush()
    return topic.id, True
