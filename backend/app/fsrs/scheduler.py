"""A simplified but real FSRS-style scheduler (Section 4.6).

Not the full 19-parameter FSRS-4.5 algorithm, but implements the same core mechanics for
real: stability and difficulty are modeled separately (unlike SM-2's single ease factor),
review timing follows the retrievability forgetting curve, and updates are weighted by the
learner's pre-reveal confidence rating rather than recall alone. This is deterministic math,
not a model call, per Section 14 ("review timing... should not carry LLM variance").
"""

MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0
DEFAULT_DIFFICULTY = 5.0
MIN_STABILITY = 0.1


def forgetting_curve(stability: float, elapsed_days: int) -> float:
    """Retrievability R(t, S) = (1 + t / (9*S)) ^ -1 — the standard FSRS forgetting curve."""
    stability = max(stability, MIN_STABILITY)
    return (1 + elapsed_days / (9 * stability)) ** -1


def update_difficulty(difficulty: float, confidence: int) -> float:
    """Confidence 0-5, collected before the answer is revealed. Higher confidence nudges
    difficulty down; low confidence nudges it up, with mean reversion toward the default
    so difficulty doesn't drift to the extremes on a single rating.
    """
    delta = (3 - confidence) * 0.5  # confidence 3 is "neutral"
    reverted = difficulty + delta - 0.1 * (difficulty - DEFAULT_DIFFICULTY)
    return min(max(reverted, MIN_DIFFICULTY), MAX_DIFFICULTY)


def update_stability(
    stability: float, difficulty: float, retrievability: float, recalled: bool, confidence: int
) -> float:
    if recalled:
        # Harder cards and cards recalled despite low retrievability gain more stability.
        confidence_weight = 0.7 + 0.15 * confidence  # low-confidence-but-correct grows stability less
        growth = (11 - difficulty) * (1 - retrievability) * confidence_weight
        return max(stability * (1 + growth * 0.3), MIN_STABILITY)
    # A lapse resets stability proportionally to how confident (and therefore surprised) the learner was.
    penalty = 0.3 + 0.1 * confidence
    return max(stability * (1 - penalty), MIN_STABILITY)


def next_interval(stability: float, target_retrievability: float = 0.9) -> int:
    """Days until retrievability is expected to decay to target_retrievability."""
    interval = 9 * stability * (1 / target_retrievability - 1)
    return max(round(interval), 1)


def fsrs_update(card: dict, confidence: int, recalled: bool) -> dict:
    """Mirrors the doc's Section 4.6 pseudocode. `card` has stability/difficulty/elapsed_days."""
    retrievability = forgetting_curve(card["stability"], card["elapsed_days"])
    difficulty = update_difficulty(card["difficulty"], confidence)
    stability = update_stability(card["stability"], difficulty, retrievability, recalled, confidence)
    interval_days = next_interval(stability)

    return {
        **card,
        "difficulty": difficulty,
        "stability": stability,
        "elapsed_days": 0,
        "next_interval_days": interval_days,
    }
