from pydantic import BaseModel


class TutorSearchRequest(BaseModel):
    subject: str
    topic_query: str
    location_lat: float | None = None
    location_lng: float | None = None
    radius_km: float = 25.0
    price_max: float | None = None
    session_format: str | None = None  # virtual|in_person|both
    verification_tier: str | None = None


class TutorResult(BaseModel):
    id: str
    name: str
    subjects: list[str]
    verification_tier: str
    rating: float
    response_time_percentile: float
    price_per_hour: float
    session_format: str
    relevance: float


class BookingHoldRequest(BaseModel):
    tutor_id: str
    learner_id: str
    slot_start: str  # ISO timestamp
