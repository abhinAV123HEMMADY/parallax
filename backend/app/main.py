from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_exam, routes_learning, routes_mastery, routes_peer, routes_protege, routes_tutors, routes_users, ws
from app.config import settings
from app.llm import llm_enabled

app = FastAPI(title="Mentra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_learning.router)
app.include_router(routes_tutors.router)
app.include_router(routes_peer.router)
app.include_router(routes_mastery.router)
app.include_router(routes_exam.router)
app.include_router(routes_protege.router)
app.include_router(routes_users.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    # llm_configured never exposes the key itself — just whether OPENAI_API_KEY loaded, so
    # a deploy issue (wrong var name, stray quotes, env not applied) is diagnosable with a
    # single curl instead of digging through logs.
    return {"status": "ok", "llm_configured": llm_enabled()}
