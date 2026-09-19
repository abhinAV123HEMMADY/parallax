from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env, resolved relative to this file rather than the process's cwd — otherwise
# whether .env actually loads depends on which directory a script happens to be run from.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Ports are 5433/6380, not the defaults — see docker-compose.yml / .env.example for why.
    database_url: str = "postgresql+asyncpg://mentra:mentra@localhost:5433/mentra"
    database_url_sync: str = "postgresql+psycopg://mentra:mentra@localhost:5433/mentra"
    redis_url: str = "redis://localhost:6380/0"

    openai_api_key: str = ""

    video_mcp_url: str = "http://localhost:8101/mcp"
    tutor_mcp_url: str = "http://localhost:8102/mcp"
    calendar_mcp_url: str = "http://localhost:8103/mcp"
    maps_mcp_url: str = "http://localhost:8104/mcp"

    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    gap_threshold: float = 0.5  # below this mastery score, prerequisite agent redirects

    # Below these, a video is left unmapped rather than attached to a plausible-but-wrong topic.
    # A wrong mapping is worse than none: it attributes the learner's attention to a concept they
    # weren't studying, and that error propagates into the peer feed and squad formation.
    note_topic_lexical_threshold: float = 0.5
    note_topic_semantic_threshold: float = 0.62

    # Screenshots are data URLs in a text column (see models/note.py). The cap is what makes
    # that survivable; the extension downscales before upload so normal frames sit far below it.
    max_screenshot_bytes: int = 200_000


settings = Settings()
