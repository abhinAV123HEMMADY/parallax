"""Turns a YouTube caption track into embeddable transcript chunks.

YouTube emits captions as cues of a few words each, a second or two apart. Storing one row per
cue would make similarity search useless in both directions: a three-word cue has almost no
semantic content to embed, and a query would match hundreds of near-identical fragments instead
of the moment that actually explains the concept. So cues are grouped into windows long enough
to carry meaning and short enough to still be a useful timestamp to jump to.

The target window is a retrieval decision, not a formatting one. Too short and chunks stop
being distinguishable; too long and the returned timestamp lands well before the relevant
sentence, which defeats the point of timestamp-level search.

Pure functions, no database and no model — the caller embeds and persists.
"""

from dataclasses import dataclass

TARGET_CHUNK_SECONDS = 45  # mid-point of the 30-60s window
MAX_CHUNK_CHARS = 1200  # bge-small truncates past ~512 tokens; stay well inside it
MAX_CUES = 20_000  # a 3h lecture is ~15k cues; beyond this the client is not sending captions
MAX_TOTAL_CHARS = 600_000


class CaptionTooLarge(ValueError):
    """Raised when a payload exceeds the ingest caps, so the route can answer 413 rather than
    embedding an unbounded amount of text synchronously inside a request."""


@dataclass
class Cue:
    t_seconds: int
    text: str


@dataclass
class Chunk:
    start_seconds: int
    text: str


def validate(cues: list[Cue]) -> None:
    if len(cues) > MAX_CUES:
        raise CaptionTooLarge(f"too many cues: {len(cues)} > {MAX_CUES}")
    total = sum(len(c.text) for c in cues)
    if total > MAX_TOTAL_CHARS:
        raise CaptionTooLarge(f"caption text too large: {total} chars > {MAX_TOTAL_CHARS}")


def group_cues(cues: list[Cue]) -> list[Chunk]:
    """Group cues into ~TARGET_CHUNK_SECONDS windows, splitting early on MAX_CHUNK_CHARS.

    A chunk's start_seconds is its first cue's timestamp, so seeking to a chunk lands at the
    beginning of the passage rather than in the middle of it.

    Cues are sorted defensively: the caption track is usually ordered, but it arrives from a
    browser extension parsing YouTube's internal format, and an out-of-order cue would otherwise
    produce a chunk whose start time is later than text it contains.
    """
    usable = [c for c in cues if c.text and c.text.strip()]
    if not usable:
        return []

    ordered = sorted(usable, key=lambda c: c.t_seconds)

    chunks: list[Chunk] = []
    current: list[Cue] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if current:
            text = " ".join(c.text.strip() for c in current)
            chunks.append(Chunk(start_seconds=current[0].t_seconds, text=" ".join(text.split())))
            current = []
            current_chars = 0

    for cue in ordered:
        span = cue.t_seconds - current[0].t_seconds if current else 0
        would_overflow = current_chars + len(cue.text) > MAX_CHUNK_CHARS
        if current and (span >= TARGET_CHUNK_SECONDS or would_overflow):
            flush()
        current.append(cue)
        current_chars += len(cue.text)

    flush()
    return chunks


def excerpt_at(chunks: list[Chunk], t_seconds: int) -> str | None:
    """The chunk covering `t_seconds` — the latest one that starts at or before it.

    Falls back to the first chunk when the timestamp precedes every chunk, which happens when a
    learner notes something in a video's opening seconds before any caption has appeared. An
    excerpt slightly after the mark is more useful than none; returning None there would make
    the composer look broken at exactly the moment a learner first tries it.
    """
    if not chunks:
        return None
    ordered = sorted(chunks, key=lambda c: c.start_seconds)
    covering = [c for c in ordered if c.start_seconds <= t_seconds]
    return (covering[-1] if covering else ordered[0]).text
