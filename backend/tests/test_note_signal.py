"""The regression tests protecting two design decisions about note signals.

1. Notes are an *attention* signal, not a mastery signal. If someone later folds notes into
   recompute_mastery, test_note_does_not_change_mastery fails.
2. A note signal has to actually clear peer/engine.py's thresholds to do anything. A fixed low
   severity would leave note signals written to the table and read by nothing, so the ramp is
   pinned here.
"""

from sqlalchemy import select

from app.mastery.service import NOTE_SIGNAL, NOTES_TO_REACH_CUTOFF, record_note_signal
from app.models import MasteryScore, StruggleEvent
from app.peer.engine import STRUGGLE_SEVERITY_CUTOFF


async def _events(db, learner_id):
    return list(
        (
            await db.execute(
                select(StruggleEvent)
                .where(StruggleEvent.user_id == learner_id, StruggleEvent.signal_type == NOTE_SIGNAL)
                .order_by(StruggleEvent.created_at)
            )
        )
        .scalars()
        .all()
    )


async def test_one_note_writes_exactly_one_event(db, learner, topic_chain):
    await record_note_signal(db, learner.id, topic_chain[0].id, share=False)
    await db.flush()
    events = await _events(db, learner.id)
    assert len(events) == 1
    assert events[0].signal_type == NOTE_SIGNAL


async def test_note_does_not_change_mastery(db, learner, topic_chain):
    """Taking a note is not evidence of understanding OR of struggling with it. A diligent
    note-taker must not score as the learner struggling most."""
    before = (
        await db.execute(
            select(MasteryScore.score).where(
                MasteryScore.user_id == learner.id, MasteryScore.topic_id == topic_chain[0].id
            )
        )
    ).scalar_one_or_none()

    for _ in range(4):
        await record_note_signal(db, learner.id, topic_chain[0].id, share=True)
        await db.flush()

    after = (
        await db.execute(
            select(MasteryScore.score).where(
                MasteryScore.user_id == learner.id, MasteryScore.topic_id == topic_chain[0].id
            )
        )
    ).scalar_one_or_none()
    assert after == before, "notes must never write MasteryScore"


async def test_severity_ramps_to_the_cutoff_on_the_third_note(db, learner, topic_chain):
    severities = []
    for _ in range(NOTES_TO_REACH_CUTOFF):
        await record_note_signal(db, learner.id, topic_chain[0].id, share=True)
        await db.flush()
        severities.append((await _events(db, learner.id))[-1].severity)

    assert severities[0] < STRUGGLE_SEVERITY_CUTOFF, "one note is not a struggle signal"
    assert severities[1] < STRUGGLE_SEVERITY_CUTOFF, "two notes are still not"
    assert severities[-1] >= STRUGGLE_SEVERITY_CUTOFF, "the third note must reach the peer cutoff"
    assert severities == sorted(severities), "severity must be monotonic in note count"


async def test_share_flag_controls_visibility(db, learner, topic_chain):
    """get_struggle_feed drops private rows, so this flag decides whether a peer ever sees it."""
    await record_note_signal(db, learner.id, topic_chain[0].id, share=False)
    await db.flush()
    assert (await _events(db, learner.id))[-1].visibility == "private"

    await record_note_signal(db, learner.id, topic_chain[1].id, share=True)
    await db.flush()
    shared = [e for e in await _events(db, learner.id) if e.topic_id == topic_chain[1].id]
    assert shared[0].visibility == "connections"


async def test_no_topic_is_a_noop(db, learner):
    """An unmapped note is a supported outcome — it must not write a signal with a null topic."""
    await record_note_signal(db, learner.id, None, share=True)
    await db.flush()
    assert await _events(db, learner.id) == []
