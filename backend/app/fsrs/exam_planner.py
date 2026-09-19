"""Exam-date-aware FSRS planning ("peak on the day").

Standard FSRS schedules each review when retrievability decays to a fixed target (0.9) and
keeps doing that forever — it optimizes indefinite retention, not readiness on a date. This
planner keeps the normal expanding-interval schedule for long-term stability, then bends the
tail of the schedule toward the exam: any card whose projected retrievability on exam day
falls below `exam_target` gets one load-balanced consolidation review placed as late as
capacity allows, so the aggregate forgetting curve peaks on the exam date instead of
sagging into it.

Deterministic math only — no LLM call, same convention as scheduler.py.
"""

from dataclasses import dataclass, field

from app.fsrs.scheduler import (
    forgetting_curve,
    next_interval,
    update_difficulty,
    update_stability,
)

EXAM_TARGET = 0.95        # desired per-card retrievability on exam day
NATURAL_TARGET = 0.9      # standard FSRS review-due threshold
CONSOLIDATION_WINDOW = 7  # consolidation reviews may land within this many days before the exam


@dataclass
class _SimCard:
    stability: float
    difficulty: float
    last_review_day: int  # negative: the last real review happened before today
    review_days: list[int] = field(default_factory=list)


def _review(card: _SimCard, day: int) -> None:
    """Apply an expected successful review (neutral confidence 3) on `day`."""
    retrievability = forgetting_curve(card.stability, day - card.last_review_day)
    card.difficulty = update_difficulty(card.difficulty, 3)
    card.stability = update_stability(card.stability, card.difficulty, retrievability, True, 3)
    card.last_review_day = day
    card.review_days.append(day)


def _natural_schedule(card: _SimCard, horizon: int) -> None:
    """Standard FSRS: review whenever retrievability hits NATURAL_TARGET, up to `horizon`."""
    while True:
        due = card.last_review_day + next_interval(card.stability, NATURAL_TARGET)
        due = max(due, 0)  # overdue cards get reviewed today, not in the past
        if due > horizon:
            return
        _review(card, due)


def _retrievability_curve(card: _SimCard, horizon: int) -> list[float]:
    """Day-by-day retrievability, replaying the card's review days with evolving stability."""
    replay = _SimCard(
        stability=card.initial_stability,  # type: ignore[attr-defined]
        difficulty=card.initial_difficulty,  # type: ignore[attr-defined]
        last_review_day=card.initial_last_review_day,  # type: ignore[attr-defined]
    )
    reviews = iter(sorted(card.review_days))
    upcoming = next(reviews, None)
    curve = []
    for day in range(horizon + 1):
        while upcoming is not None and upcoming <= day:
            _review(replay, upcoming)
            upcoming = next(reviews, None)
        curve.append(forgetting_curve(replay.stability, day - replay.last_review_day))
    return curve


def _make_sim(raw: dict) -> _SimCard:
    sim = _SimCard(
        stability=raw.get("stability", 1.0),
        difficulty=raw.get("difficulty", 5.0),
        last_review_day=-int(raw.get("elapsed_days", 0)),
    )
    # Stash initial state on the instance so the curve replay can restart from scratch.
    sim.initial_stability = sim.stability  # type: ignore[attr-defined]
    sim.initial_difficulty = sim.difficulty  # type: ignore[attr-defined]
    sim.initial_last_review_day = sim.last_review_day  # type: ignore[attr-defined]
    return sim


def _exam_day_r(card: _SimCard, exam_day: int) -> float:
    return forgetting_curve(card.stability, exam_day - card.last_review_day)


def plan_for_exam(cards: list[dict], days_until_exam: int, daily_cap: int | None = None) -> dict:
    """Compare standard FSRS against the exam-aware plan over the same deck.

    `cards`: [{front?, stability, difficulty, elapsed_days}]. Returns both projected mean
    retrievability curves, the per-card plan, and daily review load for the exam-aware plan.
    """
    exam_day = max(1, days_until_exam)
    if daily_cap is None:
        # Enough capacity that every at-risk card fits inside the consolidation window.
        daily_cap = max(3, -(-len(cards) // 3))  # ceil division

    baseline = [_make_sim(c) for c in cards]
    aware = [_make_sim(c) for c in cards]

    # Nobody reviews *on* exam day (they're sitting the exam) — both schedules stop the
    # night before, so the exam-day sample reflects genuine overnight retention.
    for card in baseline:
        _natural_schedule(card, exam_day - 1)
    for card in aware:
        _natural_schedule(card, exam_day - 1)

    # Consolidation pass: most at-risk cards first, latest day with free capacity wins.
    load: dict[int, int] = {}
    for card in aware:
        load.update({d: load.get(d, 0) + 1 for d in card.review_days})
    earliest = max(1, exam_day - CONSOLIDATION_WINDOW)
    at_risk = sorted(
        (c for c in aware if _exam_day_r(c, exam_day) < EXAM_TARGET),
        key=lambda c: _exam_day_r(c, exam_day),
    )
    for card in at_risk:
        for day in range(exam_day - 1, earliest - 1, -1):
            if load.get(day, 0) >= daily_cap or day <= card.last_review_day:
                continue
            _review(card, day)
            load[day] = load.get(day, 0) + 1
            break

    baseline_curves = [_retrievability_curve(c, exam_day) for c in baseline]
    aware_curves = [_retrievability_curve(c, exam_day) for c in aware]

    def mean_curve(curves: list[list[float]]) -> list[float]:
        if not curves:
            return [0.0] * (exam_day + 1)
        return [round(sum(c[d] for c in curves) / len(curves), 4) for d in range(exam_day + 1)]

    baseline_mean = mean_curve(baseline_curves)
    aware_mean = mean_curve(aware_curves)

    return {
        "days_until_exam": exam_day,
        "daily_cap": daily_cap,
        "curve_baseline": baseline_mean,
        "curve_exam_aware": aware_mean,
        "exam_day": {
            "baseline": baseline_mean[exam_day],
            "exam_aware": aware_mean[exam_day],
            "cards_at_risk_baseline": sum(1 for c in baseline_curves if c[exam_day] < NATURAL_TARGET),
            "cards_at_risk_exam_aware": sum(1 for c in aware_curves if c[exam_day] < NATURAL_TARGET),
        },
        "plan": [
            {
                "front": cards[i].get("front", f"card {i + 1}"),
                "review_days": sorted(aware[i].review_days),
                "projected_exam_retrievability": round(aware_curves[i][exam_day], 4),
            }
            for i in range(len(cards))
        ],
        "daily_load": [
            sum(1 for c in aware if d in c.review_days) for d in range(exam_day + 1)
        ],
    }
