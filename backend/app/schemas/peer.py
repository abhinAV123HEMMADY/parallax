from pydantic import BaseModel


class StruggleFeedItem(BaseModel):
    user_id: str
    topic_id: str
    topic_name: str
    relative_signal: str  # "struggling" | "on_track" — never a raw score, per Section 7.2


class SquadProposal(BaseModel):
    topic_id: str
    topic_name: str
    member_ids: list[str]
    shared_deck_card_ids: list[str]


class QnaPostRequest(BaseModel):
    topic_id: str
    author_id: str
    body: str
    source: str = "learner"  # learner|protege_explanation


class VisibilityUpdate(BaseModel):
    user_id: str
    topic_id: str
    visibility: str  # private|connections|cohort
