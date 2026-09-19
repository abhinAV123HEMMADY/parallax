"""Seeds demo data: a small prerequisite chain, a tutor directory, transcript chunks, a demo
connection graph, and struggle events — enough to drive every flow in the README's demo walkthrough.
"""

import asyncio
import hashlib
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session  # noqa: E402
from app.models import (  # noqa: E402
    Connection,
    MasteryScore,
    MentorProfile,
    PrerequisiteEdge,
    QnaPost,
    StruggleEvent,
    Topic,
    TutorProfile,
    User,
    VideoTranscriptChunk,
)


def pseudo_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic placeholder embedding — see mcp_servers/*/server.py for rationale.
    Duplicated here (rather than imported) so this script has no dependency on those services.
    """
    seed = int(hashlib.sha256(text.lower().encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec]


TOPIC_CHAIN = [
    ("functions", "math"),
    ("limits", "math"),
    ("derivatives", "math"),
    ("integration-basics", "math"),
    ("integration-by-parts", "math"),
]

# "derivatives" gets a rich Protégé Mode misconception set (Section 9.5) so the persona's
# questions feel genuinely naive rather than generic; keywords are what a correct explanation
# would plausibly say, used by the deterministic scorer stub to detect resolution.
DERIVATIVE_MISCONCEPTIONS = [
    {
        "id": "constant-vanishes",
        "sub_concept": "Constants have derivative zero because they don't change with x",
        "misconception_prompt": "Wait, why does the +5 just disappear when you take the derivative? Doesn't the 5 matter for the answer?",
        "keywords": ["rate of change", "doesn't change", "constant", "flat", "slope of zero", "no x"],
        "hint": "A derivative measures how much something changes as x changes. Ask yourself: does the +5 change at all as x moves?",
        "explanation": "A derivative measures the rate of change with respect to x. A constant like +5 never changes as x changes, so it contributes nothing to the rate of change — it drops out, even though the function's actual value is still shifted by 5.",
    },
    {
        "id": "power-rule-mechanics",
        "sub_concept": "The power rule multiplies by the exponent and drops it by one — the exponent doesn't just vanish",
        "misconception_prompt": "Okay so x^3 becomes x^2 — but why does the exponent just go down by one for no reason? What happened to the 3?",
        "keywords": ["multiply", "coefficient", "bring down", "n times", "n*x", "exponent minus"],
        "hint": "The 3 doesn't disappear — it moves. Try writing out x^3 as x*x*x and think about where a factor of 3 could come from.",
        "explanation": "The power rule comes from expanding x^n and differentiating term by term: the exponent becomes a multiplier out front, and the power on x drops by one — d/dx[x^3] = 3x^2. The 3 doesn't vanish, it moves from the exponent to become a coefficient.",
    },
    {
        "id": "derivative-vs-tangent-slope",
        "sub_concept": "The derivative at a point IS the slope of the tangent line there, not a separate related idea",
        "misconception_prompt": "Is the derivative a totally different thing from the slope of the tangent line, or are those actually the same number?",
        "keywords": ["tangent", "slope", "same thing", "equals the slope", "instantaneous"],
        "hint": "Picture zooming into the curve at one point until it looks like a straight line — what does that line's steepness equal?",
        "explanation": "The derivative at a point is defined exactly as the slope of the tangent line to the curve at that point — they're the same number, not two related-but-different ideas.",
    },
    {
        "id": "average-vs-instantaneous-rate",
        "sub_concept": "Average rate of change over an interval is different from the instantaneous rate at one point",
        "misconception_prompt": "If I already know the average speed over the whole trip, isn't that the same as the derivative at any moment during it?",
        "keywords": ["instantaneous", "average", "one point", "single moment", "not the same", "interval"],
        "hint": "Think of a car trip: the average speed for the whole drive can be 40mph even if the car was stopped at a light at one moment. Are those two numbers describing the same thing?",
        "explanation": "Average rate of change is the slope between two points over an interval — total change divided by total time. The derivative is the instantaneous rate at one exact point. A car's average speed for a whole trip can differ a lot from its speedometer reading at any single moment.",
    },
    {
        "id": "product-rule-not-multiply-derivatives",
        "sub_concept": "The derivative of a product isn't just the product of the two derivatives — it needs the product rule",
        "misconception_prompt": "For f(x) = x^2 * sin(x), can't I just take the derivative of x^2 and the derivative of sin(x) separately and multiply them?",
        "keywords": ["product rule", "f'g", "fg'", "first times derivative", "can't just multiply"],
        "hint": "Try it on something simple like x^2 * x^2 (which is just x^4). Does multiplying the two separate derivatives (2x)(2x) actually give you the derivative of x^4?",
        "explanation": "For a product f(x)g(x), the derivative is f'(x)g(x) + f(x)g'(x) — you can't just multiply the two derivatives together, because that misses how each function's change interacts with the other function's current value.",
    },
]

LEARNERS = [
    ("u_amy", "Amy", "10th grade"),
    ("u_ben", "Ben", "10th grade"),
    ("u_cara", "Cara", "11th grade"),
    ("u_dev", "Dev", "11th grade"),
    ("u_ella", "Ella", "10th grade"),
]

TUTORS = [
    ("t_maria", "Maria Chen", ["math", "calculus"], "background_checked", 4.9, 0.95, 45.0, "both", 37.77, -122.42),
    ("t_sam", "Sam Okafor", ["math"], "basic", 4.6, 0.8, 30.0, "virtual", None, None),
    ("t_ravi", "Ravi Patel", ["math", "physics"], "background_checked", 4.8, 0.9, 55.0, "in_person", 37.80, -122.27),
]


async def main():
    async with async_session() as db:
        # None of these models declare an ORM relationship() to each other (plain FK columns
        # only), so SQLAlchemy has no dependency graph to auto-order inserts across tables —
        # each layer below must be flushed before the next layer that FK-references it is added.

        # --- Topics ---
        for name, subject in TOPIC_CHAIN:
            db.add(
                Topic(
                    id=name,
                    name=name.replace("-", " "),
                    subject=subject,
                    content_embedding=pseudo_embed(name),
                    common_misconceptions=DERIVATIVE_MISCONCEPTIONS if name == "derivatives" else None,
                )
            )
        await db.flush()

        # --- Prerequisite chain (FKs to topics) ---
        for i in range(1, len(TOPIC_CHAIN)):
            topic_id = TOPIC_CHAIN[i][0]
            prereq_id = TOPIC_CHAIN[i - 1][0]
            db.add(PrerequisiteEdge(topic_id=topic_id, prerequisite_topic_id=prereq_id))

        # --- Learners ---
        for user_id, name, grade in LEARNERS:
            db.add(User(id=user_id, name=name, grade_level=grade, goals=["ace calculus"]))
        await db.flush()  # users must exist before mastery/connection/struggle rows below

        # u_amy is weak on "limits" so a "derivatives" request redirects to it (Section 4.2 demo).
        db.add(MasteryScore(user_id="u_amy", topic_id="limits", score=0.2))
        db.add(MasteryScore(user_id="u_amy", topic_id="functions", score=0.9))

        # --- Connection graph: amy-ben-cara mutually connected, dev connected to amy only ---
        for a, b in [("u_amy", "u_ben"), ("u_amy", "u_cara"), ("u_ben", "u_cara"), ("u_amy", "u_dev")]:
            db.add(Connection(user_id_a=a, user_id_b=b, status="connected"))

        # --- Struggle events: amy, ben, cara all struggling with derivatives -> squad-eligible ---
        for user_id in ["u_amy", "u_ben", "u_cara"]:
            db.add(
                StruggleEvent(
                    id=f"se_{user_id}_derivatives",
                    user_id=user_id,
                    topic_id="derivatives",
                    signal_type="quiz_miss",
                    severity=0.7,
                    visibility="connections",
                )
            )

        # --- Mentor track: dev has high mastery on functions, opts in as an informal peer mentor ---
        db.add(MasteryScore(user_id="u_dev", topic_id="functions", score=0.95))
        db.add(MentorProfile(user_id="u_dev", topic_id="functions", mastery_score=0.95))

        # --- Q&A seed ---
        db.add(
            QnaPost(
                id="qna_1",
                topic_id="derivatives",
                author_id="u_ben",
                body="Why does the power rule drop the exponent by one?",
                moderation_status="approved",
            )
        )

        # --- Tutors ---
        for tid, name, subjects, tier, rating, resp, price, fmt, lat, lng in TUTORS:
            db.add(
                TutorProfile(
                    id=tid,
                    name=name,
                    subjects=subjects,
                    specialty_embedding=pseudo_embed(" ".join(subjects) + " " + name),
                    location_lat=lat,
                    location_lng=lng,
                    verification_tier=tier,
                    response_time_percentile=resp,
                    rating=rating,
                    price_per_hour=price,
                    session_format=fmt,
                )
            )

        # --- Video transcript chunks ---
        # Real Khan Academy YouTube videos (verified to exist) so clicking through in the demo
        # actually plays something, rather than placeholder IDs that 404 on YouTube.
        video_seed = [
            ("riXcZT2ICjA", "Introduction to limits | Khan Academy", 30, "A limit describes what a function approaches.", "intro"),
            ("W0VWO4asgmk", "Introduction to limits 2 | Khan Academy", 60, "Formal epsilon-delta definition of a limit.", "advanced"),
            ("fI6w2kL295Y", "Approximating instantaneous rate of change | Khan Academy", 45, "The derivative is the instantaneous rate of change.", "intro"),
            ("dh__n9FVKA0", "Integration by parts intro | Khan Academy", 30, "Integration by parts reverses the product rule.", "intermediate"),
        ]
        for video_id, title, start, chunk_text, difficulty in video_seed:
            db.add(
                VideoTranscriptChunk(
                    id=f"chunk_{video_id}",
                    video_id=video_id,
                    video_title=title,
                    chunk_start_seconds=start,
                    chunk_text=chunk_text,
                    difficulty_level=difficulty,
                    chunk_embedding=pseudo_embed(title + " " + chunk_text),
                )
            )

        await db.commit()
    print("Seed data loaded.")


if __name__ == "__main__":
    asyncio.run(main())
