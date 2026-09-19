"""Calendar / Booking MCP Server (Section 5.3).

get_availability computes genuinely open slots by diffing a generated weekly schedule
against real rows in the bookings table; create_booking_hold writes a real hold that
expires in 15 minutes if not confirmed, preventing double-booking.
"""

import os
import uuid
from datetime import datetime, timedelta

import asyncpg
from mcp.server.fastmcp import FastMCP

DATABASE_URL = os.environ.get("MCP_DATABASE_URL", "postgresql://mentra:mentra@localhost:5433/mentra")
PORT = int(os.environ.get("PORT", 8103))

mcp = FastMCP("calendar-booking-mcp", port=PORT)
_pool: asyncpg.Pool | None = None

HOLD_MINUTES = 15
BUSINESS_HOURS = range(9, 17)  # 9am-5pm


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


def _week_slots(week_start: datetime) -> list[datetime]:
    slots = []
    for day_offset in range(5):  # Mon-Fri
        day = week_start + timedelta(days=day_offset)
        slots.extend(day.replace(hour=h, minute=0, second=0, microsecond=0) for h in BUSINESS_HOURS)
    return slots


@mcp.tool()
async def get_availability(tutor_id: str, week: str) -> list[str]:
    """`week` is an ISO date (any day in the target week); returns open ISO-timestamp slots."""
    week_start = datetime.fromisoformat(week)
    week_start -= timedelta(days=week_start.weekday())  # snap to Monday
    all_slots = _week_slots(week_start)

    pool = await get_pool()
    async with pool.acquire() as conn:
        taken_rows = await conn.fetch(
            """
            SELECT slot_start FROM bookings
            WHERE tutor_id = $1
              AND status IN ('confirmed', 'hold')
              AND (status = 'confirmed' OR hold_expires_at > now())
            """,
            tutor_id,
        )
    taken = {row["slot_start"] for row in taken_rows}

    return [slot.isoformat() for slot in all_slots if slot.replace(tzinfo=None) not in {t.replace(tzinfo=None) for t in taken}]


@mcp.tool()
async def create_booking_hold(tutor_id: str, learner_id: str, slot: str) -> dict:
    """Places a 15-minute hold on `slot`. Fails if the slot already has a live hold/confirmation."""
    slot_start = datetime.fromisoformat(slot)
    now = datetime.utcnow()
    hold_expires_at = now + timedelta(minutes=HOLD_MINUTES)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            conflict = await conn.fetchrow(
                """
                SELECT id FROM bookings
                WHERE tutor_id = $1 AND slot_start = $2
                  AND (status = 'confirmed' OR (status = 'hold' AND hold_expires_at > now()))
                """,
                tutor_id,
                slot_start,
            )
            if conflict:
                return {"status": "conflict", "booking_id": None}

            booking_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO bookings (id, tutor_id, learner_id, slot_start, status, hold_expires_at)
                VALUES ($1, $2, $3, $4, 'hold', $5)
                """,
                booking_id,
                tutor_id,
                learner_id,
                slot_start,
                hold_expires_at,
            )

    return {"status": "hold", "booking_id": booking_id, "hold_expires_at": hold_expires_at.isoformat()}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
