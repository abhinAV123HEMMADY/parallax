from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    name: str
    grade_level: str | None = None


class UserCreateRequest(BaseModel):
    name: str
    grade_level: str | None = None
