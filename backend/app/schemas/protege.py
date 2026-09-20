from datetime import datetime

from pydantic import BaseModel


class ChecklistItem(BaseModel):
    id: str
    sub_concept: str
    covered: bool


class ProtegeStartRequest(BaseModel):
    topic_name: str
    learner_id: str


class ProtegeTurnRequest(BaseModel):
    session_id: str
    learner_explanation: str


class ProtegePublishRequest(BaseModel):
    session_id: str


class ProtegeTurnResult(BaseModel):
    session_id: str
    topic_name: str
    persona_message: str
    understanding_score: float
    checklist: list[ChecklistItem]
    resolved_misconceptions: list[str]
    status: str  # active|completed


class ProtegeRecapResult(BaseModel):
    session_id: str
    topic_id: str
    topic_name: str
    summary: str
    taught_well: list[str]
    still_shaky: list[str]
    understanding_score: float
    turn_count: int
    created_at: datetime
