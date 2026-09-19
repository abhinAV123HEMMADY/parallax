"""Interaction-driven mastery scoring (Section 4.7, 9.5).

Mastery is recomputed from what the learner has actually done — never at content-generation
time. The three signals, all read back from real persisted interactions:

  - quiz accuracy: QuizAttempt rows the learner self-graded after answering
  - flashcard confidence: pre-reveal ConfidenceRating rows from real card reviews
  - protégé teach-back: the latest completed/published ProtegeSession's understanding score

Weights renormalize over whichever signals exist yet, so a learner who has only answered
quiz questions isn't capped by the signals they haven't produced. With no interactions at
all there is no row — the topic stays genuinely untouched.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ConfidenceRating, Flashcard, Lesson, MasteryScore, ProtegeSession, QuizAttempt, StruggleEvent

QUIZ_WEIGHT = 0.35
FLASHCARD_WEIGHT = 0.25
PROTEGE_WEIGHT = 0.40  # a generative demonstration of understanding is harder to fake than
# recognizing an answer or self-rating confidence — weighted highest (Section 9.5).


async def recompute_mastery(db: AsyncSession, learner_id: str, topic_id: str) -> float | None:
    """Recomputes and upserts the learner's mastery on a topic from real interactions.

    Returns the new score, or None when the learner hasn't interacted with the topic at all
    (in which case nothing is written and the topic stays untouched). Does not commit —
    the calling route owns the transaction.
    """
    lesson_ids = (
        (await db.execute(
            select(Lesson.id).where(Lesson.learner_id == learner_id, Lesson.topic_id == topic_id)
        )).scalars().all()
    )

    quiz_accuracy = None
    if lesson_ids:
        attempts = (
            (await db.execute(
                select(QuizAttempt.correct).where(QuizAttempt.lesson_id.in_(lesson_ids))
            )).scalars().all()
        )
        if attempts:
            quiz_accuracy = sum(1 for c in attempts if c) / len(attempts)

    confidence_signal = None
    strong_struggle = False
    if lesson_ids:
        ratings = (
            (await db.execute(
                select(ConfidenceRating.rating)
                .join(Flashcard, ConfidenceRating.card_id == Flashcard.id)
                .where(Flashcard.lesson_id.in_(lesson_ids), ConfidenceRating.learner_id == learner_id)
            )).scalars().all()
        )
        if ratings:
            # Low confidence paired with a review is a calibration signal: each shaky rating
            # chips away at the flashcard component, and a bottomed-out rating flags struggle.
            calibration_penalty = 0.0
            for rating in ratings:
                if rating <= 1:
                    strong_struggle = True
                    calibration_penalty += 0.15
                elif rating <= 2:
                    calibration_penalty += 0.05
            confidence_signal = max(0.0, 1 - calibration_penalty)

    protege_score = (
        await db.execute(
            select(ProtegeSession.understanding_score)
            .where(
                ProtegeSession.learner_id == learner_id,
                ProtegeSession.topic_id == topic_id,
                ProtegeSession.status.in_(["completed", "published"]),
            )
            .order_by(ProtegeSession.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    signals = [
        (quiz_accuracy, QUIZ_WEIGHT),
        (confidence_signal, FLASHCARD_WEIGHT),
        (protege_score, PROTEGE_WEIGHT),
    ]
    present = [(value, weight) for value, weight in signals if value is not None]
    if not present:
        return None

    total_weight = sum(weight for _, weight in present)
    mastery = round(sum(value * weight for value, weight in present) / total_weight, 3)

    stmt = insert(MasteryScore).values(user_id=learner_id, topic_id=topic_id, score=mastery)
    stmt = stmt.on_conflict_do_update(
        index_elements=[MasteryScore.user_id, MasteryScore.topic_id], set_={"score": mastery}
    )
    await db.execute(stmt)

    if strong_struggle or mastery < settings.gap_threshold:
        db.add(
            StruggleEvent(
                id=str(uuid.uuid4()),
                user_id=learner_id,
                topic_id=topic_id,
                signal_type="quiz_miss" if (quiz_accuracy or 1.0) < 0.5 else "low_confidence_correct",
                severity=round(1 - mastery, 3),
                visibility="private",  # learner opts in to sharing later (Section 7.2)
            )
        )

    return mastery
