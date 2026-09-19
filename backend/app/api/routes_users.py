import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.user import UserCreateRequest, UserOut

router = APIRouter(prefix="/users", tags=["users"])


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(User).order_by(User.name))).scalars().all()
    return [UserOut(id=u.id, name=u.name, grade_level=u.grade_level) for u in users]


@router.post("", response_model=UserOut)
async def create_user(req: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    """Creates a fresh learner profile. New profiles start with zero history everywhere —
    mastery, cards, sessions — so every number they ever see is one they earned."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    user_id = f"u_{_slugify(name)}" or f"u_{uuid.uuid4().hex[:8]}"
    if await db.get(User, user_id) is not None:
        user_id = f"{user_id}-{uuid.uuid4().hex[:4]}"

    user = User(id=user_id, name=name, grade_level=req.grade_level, goals=[])
    db.add(user)
    await db.commit()
    return UserOut(id=user.id, name=user.name, grade_level=user.grade_level)
