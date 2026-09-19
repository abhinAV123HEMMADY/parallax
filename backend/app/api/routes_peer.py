import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import QnaPost
from app.moderation.service import moderate_text
from app.peer.engine import get_struggle_feed, persist_squad_proposals, propose_squads_for_topic
from app.schemas.peer import QnaPostRequest

router = APIRouter(prefix="/peer", tags=["peer"])


@router.get("/feed/{user_id}")
async def struggle_feed(user_id: str, db: AsyncSession = Depends(get_db)):
    return await get_struggle_feed(db, user_id)


@router.get("/squads/{topic_id}")
async def propose_squads(topic_id: str, db: AsyncSession = Depends(get_db)):
    proposals = await propose_squads_for_topic(db, topic_id)
    squads = await persist_squad_proposals(db, proposals)
    return [{"id": s.id, "topic_id": s.topic_id, "member_ids": s.member_ids} for s in squads]


@router.post("/qna")
async def create_qna_post(req: QnaPostRequest, db: AsyncSession = Depends(get_db)):
    """Every Q&A post passes through moderation before other learners can see it (Section 7.2)."""
    status = moderate_text(req.body)
    post = QnaPost(
        id=str(uuid.uuid4()), topic_id=req.topic_id, author_id=req.author_id, body=req.body,
        moderation_status=status, source=req.source,
    )
    db.add(post)
    await db.commit()
    return {"id": post.id, "moderation_status": status}
