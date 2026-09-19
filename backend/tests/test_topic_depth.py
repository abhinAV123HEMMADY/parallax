"""Prerequisite depth, including the cycle guard.

PrerequisiteEdge is a plain two-column table with nothing preventing A->B->A. Without a visited
set an unguarded walk would spin forever inside a request, so the cycle test is the important one.
"""

from app.models import PrerequisiteEdge
from app.topics.graph import depths_for, topic_depth, upstream_of


async def test_depth_along_a_chain(db, topic_chain):
    basics, middle, advanced = topic_chain
    assert await topic_depth(db, basics.id) == 0
    assert await topic_depth(db, middle.id) == 1
    assert await topic_depth(db, advanced.id) == 2


async def test_upstream_returns_immediate_prerequisites_only(db, topic_chain):
    basics, middle, advanced = topic_chain
    assert [t.id for t in await upstream_of(db, advanced.id)] == [middle.id]
    assert [t.id for t in await upstream_of(db, middle.id)] == [basics.id]
    assert await upstream_of(db, basics.id) == []


async def test_cycle_terminates(db, topic_chain):
    """Closing the chain into a loop must not hang."""
    basics, _, advanced = topic_chain
    db.add(PrerequisiteEdge(topic_id=basics.id, prerequisite_topic_id=advanced.id))
    await db.flush()

    depth = await topic_depth(db, advanced.id)
    assert isinstance(depth, int)
    assert depth <= 32, "must be bounded by MAX_DEPTH rather than looping"


async def test_depths_for_batches(db, topic_chain):
    ids = [t.id for t in topic_chain]
    depths = await depths_for(db, ids + [ids[0]])
    assert depths == {ids[0]: 0, ids[1]: 1, ids[2]: 2}
