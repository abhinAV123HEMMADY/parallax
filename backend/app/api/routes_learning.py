import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.fsrs.scheduler import fsrs_update
from app.mastery.service import recompute_mastery
from app.models import ConfidenceRating, Flashcard, Lesson, QuizAttempt
from app.schemas.learning import ConfidenceSubmission, LearnAccepted, LearnRequest, QuizAnswerSubmission
from app.tasks import run_learning_pipeline

router = APIRouter(prefix="/learn", tags=["learning"])


@router.post("", response_model=LearnAccepted)
async def start_learning(req: LearnRequest):
    session_id = str(uuid.uuid4())
    run_learning_pipeline.delay(session_id, req.learner_id, req.topic_input, req.input_mode)
    return LearnAccepted(session_id=session_id)


@router.post("/quiz-answer")
async def submit_quiz_answer(payload: QuizAnswerSubmission, db: AsyncSession = Depends(get_db)):
    """Records a real, learner-graded quiz answer and folds it into mastery (Section 4.7).

    This is the only place quiz outcomes enter the system — generation never pre-fills them.
    """
    lesson = await db.get(Lesson, payload.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="lesson not found")

    db.add(
        QuizAttempt(
            id=str(uuid.uuid4()),
            lesson_id=payload.lesson_id,
            question=payload.question,
            correct=payload.correct,
            modality_used=payload.modality_used,
        )
    )
    await db.flush()

    mastery = await recompute_mastery(db, lesson.learner_id, lesson.topic_id)
    await db.commit()
    return {"status": "ok", "mastery_score": mastery, "topic_id": lesson.topic_id}


@router.post("/confidence")
async def submit_confidence(payload: ConfidenceSubmission, db: AsyncSession = Depends(get_db)):
    """Applies a real FSRS update to the reviewed card, records the pre-reveal confidence
    rating, and folds the review into mastery."""
    card = await db.get(Flashcard, payload.card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")

    updated = fsrs_update(
        {"stability": card.stability, "difficulty": card.difficulty, "elapsed_days": card.elapsed_days},
        payload.rating,
        payload.recalled,
    )
    card.stability = updated["stability"]
    card.difficulty = updated["difficulty"]
    card.elapsed_days = 0
    card.due_date = datetime.utcnow() + timedelta(days=updated["next_interval_days"])

    db.add(
        ConfidenceRating(
            id=str(uuid.uuid4()),
            card_id=payload.card_id,
            learner_id=payload.learner_id,
            rating=payload.rating,
        )
    )
    await db.flush()

    lesson = await db.get(Lesson, card.lesson_id)
    mastery = await recompute_mastery(db, payload.learner_id, lesson.topic_id) if lesson else None
    await db.commit()

    return {
        "status": "ok",
        "next_due_days": updated["next_interval_days"],
        "mastery_score": mastery,
        "topic_id": lesson.topic_id if lesson else None,
    }
