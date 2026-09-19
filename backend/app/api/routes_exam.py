"""Exam-date-aware review planning endpoint ("peak on the day").

Pulls the learner's real flashcard deck (FSRS state included) and asks the exam planner to
bend the review schedule so aggregate retrievability peaks on the exam date. When the
learner has no cards yet, a representative demo deck is planned instead so the feature
always demos — flagged `demo_deck` so the UI can say so.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.fsrs.exam_planner import plan_for_exam
from app.models import Flashcard, Lesson

router = APIRouter(prefix="/exam", tags=["exam"])


class ExamPlanRequest(BaseModel):
    learner_id: str
    days_until_exam: int = Field(ge=1, le=180)
    topic_id: str | None = None


def _demo_deck() -> list[dict]:
    """A fixed, varied deck: fresh cards, well-known cards, and neglected decaying ones."""
    deck = []
    for i in range(18):
        deck.append(
            {
                "front": f"demo card {i + 1}",
                "stability": [0.8, 2.0, 4.5, 9.0, 16.0, 28.0][i % 6],
                "difficulty": [3.5, 5.0, 6.5][i % 3],
                "elapsed_days": [0, 2, 5, 9, 14, 21][i % 6],
            }
        )
    return deck


@router.post("/plan")
async def exam_plan(req: ExamPlanRequest, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Flashcard.front, Flashcard.stability, Flashcard.difficulty, Flashcard.elapsed_days)
        .join(Lesson, Flashcard.lesson_id == Lesson.id)
        .where(Lesson.learner_id == req.learner_id)
    )
    if req.topic_id:
        stmt = stmt.where(Lesson.topic_id == req.topic_id)

    rows = (await db.execute(stmt)).all()
    cards = [
        {"front": r.front, "stability": r.stability, "difficulty": r.difficulty, "elapsed_days": r.elapsed_days}
        for r in rows
    ]

    demo = not cards
    if demo:
        cards = _demo_deck()

    plan = plan_for_exam(cards, req.days_until_exam)
    plan["demo_deck"] = demo
    plan["card_count"] = len(cards)
    return plan
