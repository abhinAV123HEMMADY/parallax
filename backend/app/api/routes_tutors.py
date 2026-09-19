from fastapi import APIRouter

from app.mcp_clients import create_booking_hold, find_tutors, get_availability, nearby_tutors
from app.schemas.tutor import BookingHoldRequest, TutorSearchRequest

router = APIRouter(prefix="/tutors", tags=["tutors"])


@router.post("/search")
async def search_tutors(req: TutorSearchRequest):
    return await find_tutors(
        subject=req.subject,
        topic_query=req.topic_query,
        location_lat=req.location_lat,
        location_lng=req.location_lng,
        radius_km=req.radius_km,
        price_max=req.price_max,
        session_format=req.session_format,
        verification_tier=req.verification_tier,
    )


@router.get("/nearby")
async def search_nearby(lat: float, lng: float, radius_km: float = 25.0):
    return await nearby_tutors(lat, lng, radius_km)


@router.get("/{tutor_id}/availability")
async def availability(tutor_id: str, week: str):
    return await get_availability(tutor_id, week)


@router.post("/book")
async def book(req: BookingHoldRequest):
    """Creates a 15-minute booking hold against the Calendar MCP server (Section 5.3)."""
    return await create_booking_hold(req.tutor_id, req.learner_id, req.slot_start)
