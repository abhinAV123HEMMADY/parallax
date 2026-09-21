"""Topic auto-creation: naming, de-duplication, and the match-first guarantee.

The naming tests assert the *name a learner would recognise*, not that a string came back.
That distinction matters here for the same reason it does in test_embedding.py: the earlier
version of this code passed every "returns a non-empty name" check while emitting "revolution
french" and "electron configuration understanding", which are names nobody would file a note
under. Word order and filler removal are the behaviour, so they are what's asserted.

The de-duplication tests pin naming to the deterministic path on purpose. They are about whether
two names collapse to one topic, and a live model renames the same video differently on every
call — which would make them assert the model's consistency rather than the dedupe logic.
"""

import uuid

import pytest

from app.config import settings
from app.models import Topic
from app.notes.topic_autocreate import (
    ensure_topic,
    find_equivalent,
    propose_from_text,
    slugify,
)


@pytest.fixture
def deterministic_naming(monkeypatch):
    """Pins naming to the deterministic path by clearing the key `llm_enabled()` reads.

    These tests are about de-duplication, not about what a model happens to name something. With
    a key configured the name varies per call, so asserting on dedupe requires naming held still
    — and it must hold still on a machine that *has* a key, not only on one that happens not to.
    """
    monkeypatch.setattr(settings, "openai_api_key", "")


def test_strips_lecture_packaging_and_keeps_title_order():
    proposal = propose_from_text(
        "Lecture 7: Understanding Electron Configuration",
        "electron electron configuration orbital shells",
    )
    assert proposal.name == "electron configuration"
    assert proposal.slug == "electron-configuration"


def test_preserves_title_word_order_regardless_of_transcript_frequency():
    """"revolution" dominates the transcript, but the concept is still "french revolution"."""
    proposal = propose_from_text(
        "The French Revolution Explained",
        "revolution revolution revolution france king louis",
    )
    assert proposal.name == "french revolution"


def test_drops_episode_numbers_and_years():
    proposal = propose_from_text("CS50 2023 - Lecture 4 - Memory", "memory pointer malloc")
    assert "2023" not in proposal.name
    assert "4" not in proposal.name
    assert "memory" in proposal.name


def test_drops_course_label_when_a_concept_survives():
    proposal = propose_from_text(
        "Photosynthesis: Crash Course Biology #8", "photosynthesis light chloroplast"
    )
    assert proposal.name == "photosynthesis"


def test_keeps_course_label_when_it_is_all_there_is():
    """"Biology" is the only content word — dropping it would leave nothing to file under."""
    proposal = propose_from_text("Biology Basics", "cell life organism")
    assert proposal.name == "biology"


def test_falls_back_to_the_title_when_no_token_survives():
    proposal = propose_from_text("!!!", "nothing useful")
    assert proposal.name
    assert proposal.slug


def test_caps_name_length():
    proposal = propose_from_text(
        "Supply Demand Elasticity Equilibrium Monopoly Inflation Deficit",
        "supply demand elasticity equilibrium monopoly inflation deficit",
    )
    assert len(proposal.name.split()) <= 4


def test_slugify_handles_punctuation():
    assert slugify("Electron Configuration!") == "electron-configuration"
    assert slugify("  spaced  out  ") == "spaced-out"


async def test_ensure_topic_creates_then_reuses(db, deterministic_naming):
    title = f"Understanding Zorbital Fluxing {uuid.uuid4().hex[:6]}"
    transcript = "zorbital fluxing is the process by which zorbitals flux"

    first_id, created_first = await ensure_topic(db, title, transcript)
    assert created_first is True

    second_id, created_second = await ensure_topic(db, title, transcript)
    assert second_id == first_id
    assert created_second is False, "a second note on the same video must not mint a second topic"


async def test_near_duplicate_name_merges_instead_of_splitting(db, deterministic_naming):
    """A plural or reworded title is the same concept, and must not split the node in two."""
    suffix = uuid.uuid4().hex[:6]
    first_id, _ = await ensure_topic(
        db, f"Electron Configuration {suffix}", "electrons fill orbitals by energy"
    )
    second_id, created = await ensure_topic(
        db, f"Electron Configurations {suffix}", "electrons filling orbitals by energy"
    )
    assert second_id == first_id
    assert created is False


async def test_created_topic_carries_no_curriculum_claims(db, deterministic_naming):
    """Discovered from a video, so it holds notes without posing as an authored curriculum node."""
    topic_id, _ = await ensure_topic(
        db, f"Quantum Zorbitals {uuid.uuid4().hex[:6]}", "zorbital spin states"
    )
    topic = await db.get(Topic, topic_id)
    assert topic.common_misconceptions is None
    assert topic.content_embedding is not None, "must be embeddable, or dedupe can't see it"


async def test_unrelated_subjects_do_not_merge(db, deterministic_naming):
    suffix = uuid.uuid4().hex[:6]
    chem_id, _ = await ensure_topic(db, f"Electron Configuration {suffix}", "orbitals and shells")
    hist_id, _ = await ensure_topic(db, f"French Revolution {suffix}", "louis the sixteenth")
    assert chem_id != hist_id


async def test_same_video_reuses_its_first_topic_even_when_the_name_changes(db, learner):
    """The guarantee that survives naming drift.

    A model names a video "pointers and memory allocation"; a rate limit later sends the same
    video to the deterministic fallback, which names it "cs50 memory". Those are far enough
    apart to clear the near-duplicate threshold, so without an exact per-video check the video
    would fork into two topics and split its own notes.
    """
    from app.models import VideoNote

    video_id = f"vid_{uuid.uuid4().hex[:8]}"
    first_id, created = await ensure_topic(
        db, "Pointers and Memory Allocation", "malloc and addresses", video_id=video_id
    )
    assert created is True

    db.add(
        VideoNote(
            id=str(uuid.uuid4()),
            learner_id=learner.id,
            video_id=video_id,
            video_title="Pointers and Memory Allocation",
            topic_id=first_id,
            t_seconds=10,
            learner_text="note",
        )
    )
    await db.flush()

    # Same video, a name nothing would merge with on similarity alone.
    second_id, created_again = await ensure_topic(
        db, "CS50 2023 - Lecture 4 - Memory", "malloc and addresses", video_id=video_id
    )
    assert second_id == first_id
    assert created_again is False


async def test_find_equivalent_returns_none_for_a_novel_concept(db, deterministic_naming):
    from app.notes.topic_autocreate import ProposedTopic

    novel = ProposedTopic(
        name=f"zorbital fluxing {uuid.uuid4().hex[:6]}",
        subject="general",
        slug=f"zorbital-fluxing-{uuid.uuid4().hex[:6]}",
    )
    assert await find_equivalent(db, novel) is None
