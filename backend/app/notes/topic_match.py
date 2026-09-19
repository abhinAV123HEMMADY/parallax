"""Maps an arbitrary YouTube video to a Mentra topic, or to nothing.

A note taken on YouTube has no topic attached — the learner is on a video, not in a lesson. But
a note only reaches the peer layer and the flashcard generator if it has a `topic_id`, so a
guess is worth making. A *wrong* guess is not: it would attribute a learner's attention to a
concept they weren't studying, and that error propagates into the struggle feed and squads.
So both strategies here return None below a confidence threshold, and an unmapped note is a
supported outcome rather than a failure.

Two strategies, deliberately kept side by side so `/topic-suggestion` can report both and the
default can be chosen on evidence:

  lexical  — token overlap against Topic.name. Deterministic, explainable, no model.
  semantic — nearest Topic.content_embedding by pgvector cosine distance.

Semantic is not automatically the better one here. Topic.content_embedding is built from the
topic *name* alone (see scripts/seed.py), so the semantic path compares a video title and
transcript against an embedding of a two-word label — a much weaker comparison than
document-to-document, and one where a long title's unrelated words drag the score around.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mentra_embed import embed_query

from app.models import Topic

# Words that appear in lecture titles without saying anything about the subject. Without this,
# "Introduction to limits" and "Introduction to integration" share a token and every topic looks
# equally plausible for any video whose title starts the same way.
_NOISE = {
    "a", "an", "the", "to", "of", "in", "on", "for", "and", "or", "with", "how", "what", "why",
    "intro", "introduction", "basics", "basic", "tutorial", "lesson", "lecture", "part",
    "explained", "example", "examples", "khan", "academy", "video", "full", "course",
}


@dataclass
class TopicSuggestion:
    topic_id: str | None
    topic_name: str | None
    score: float
    strategy: str


def _tokens(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if w and w not in _NOISE and len(w) > 2}


def lexical_suggestion(
    video_title: str, transcript: str, topics: list[Topic], threshold: float
) -> TopicSuggestion:
    """Best topic by token overlap, scored as the fraction of the *topic's* tokens present.

    Normalising by the topic's token count rather than the video's is what makes this work: a
    topic name is two or three words, a transcript is thousands, so dividing by the union would
    drive every score to near zero. Asking "how much of this topic's vocabulary appears here"
    keeps short topic names comparable with long ones.
    """
    haystack = _tokens(video_title) | _tokens(transcript)
    best = TopicSuggestion(None, None, 0.0, "lexical")

    for topic in topics:
        topic_tokens = _tokens(topic.name)
        if not topic_tokens:
            continue
        # Title matches are worth more than transcript matches: a lecture titled "limits" is
        # about limits, whereas a transcript can mention limits once in passing.
        title_hits = len(topic_tokens & _tokens(video_title))
        overlap = len(topic_tokens & haystack)
        score = overlap / len(topic_tokens)
        if title_hits:
            score = min(1.0, score + 0.25 * (title_hits / len(topic_tokens)))
        if score > best.score:
            best = TopicSuggestion(topic.id, topic.name, round(score, 4), "lexical")

    return best if best.score >= threshold else TopicSuggestion(None, None, best.score, "lexical")


async def semantic_suggestion(
    db: AsyncSession, video_title: str, transcript: str, threshold: float
) -> TopicSuggestion:
    """Nearest topic by embedding. Uses embed_query because the stored side is a short label,
    which is the asymmetric query-to-passage case bge's query prefix is trained for."""
    # A long transcript would swamp the title; the title is the strongest single signal about
    # what a lecture is about, so it leads and the transcript only adds context.
    probe = f"{video_title}. {transcript[:1000]}"
    vector = embed_query(probe)

    row = (
        await db.execute(
            select(Topic.id, Topic.name, (1 - Topic.content_embedding.cosine_distance(vector)).label("score"))
            .where(Topic.content_embedding.isnot(None))
            .order_by(Topic.content_embedding.cosine_distance(vector))
            .limit(1)
        )
    ).first()

    if row is None:
        return TopicSuggestion(None, None, 0.0, "semantic")

    topic_id, topic_name, score = row
    score = round(float(score), 4)
    if score < threshold:
        return TopicSuggestion(None, None, score, "semantic")
    return TopicSuggestion(topic_id, topic_name, score, "semantic")


async def suggest_topic(
    db: AsyncSession,
    video_title: str,
    transcript: str,
    lexical_threshold: float,
    semantic_threshold: float,
) -> dict:
    """Runs both strategies and returns both, plus the one to use.

    Lexical wins ties and wins outright when it fires, because an explicit name match is
    evidence a learner can verify at a glance, whereas a 0.6 cosine score is not. Semantic is
    the fallback for paraphrased titles that share no words with any topic name.
    """
    topics = list((await db.execute(select(Topic))).scalars().all())
    lexical = lexical_suggestion(video_title, transcript, topics, lexical_threshold)
    semantic = await semantic_suggestion(db, video_title, transcript, semantic_threshold)

    chosen = lexical if lexical.topic_id else semantic
    return {
        "chosen": chosen,
        "lexical": lexical,
        "semantic": semantic,
    }
