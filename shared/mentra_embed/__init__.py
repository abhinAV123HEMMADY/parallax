"""Single source of truth for text embeddings, shared by the backend and the MCP servers.

This package deliberately breaks a rule the MCP servers were written to: each server used to
carry its own copy of `pseudo_embed` so it stayed a standalone process with no shared
dependency (see the comment this replaced in mcp_servers/video_transcript/server.py). That
duplication was free for a hash function. It is not free for a real model — three servers plus
the backend plus every Celery prefork worker would each hold their own 130MB ONNX session, and
four copies of the chunking/prefix conventions would drift apart the first time one changed.
One installable package is the lesser cost.

Why embeddings had to become real: the previous `pseudo_embed` hashed the string, seeded an RNG
and returned a random unit vector, so cosine similarity between any two distinct strings was
noise. Measured on the old function, "limits" vs "Introduction to limits | Khan Academy" scored
-0.043 — a topic scored *negatively* against its own matching video title, meaning every
pgvector ranking in the system was arbitrary. The same pair scores +0.813 here.

Backends:
  bge  (default) BAAI/bge-small-en-v1.5 via fastembed. 384-dim, which is exactly
       EMBEDDING_DIM in backend/app/models/topic.py, so switching needed no migration.
       ONNX runtime, so no PyTorch dependency.
  hash the old deterministic placeholder, kept so the project still runs where the model
       cannot be downloaded (air-gapped CI, a machine with no disk budget). Rankings are
       meaningless under it — it exists to keep things importable, not useful.

Select with the MENTRA_EMBED environment variable. Read from the environment rather than from
app.config because the MCP servers are independent processes that never import the backend's
settings module.
"""

import hashlib
import os
import random
import threading

# Must stay in sync with EMBEDDING_DIM in backend/app/models/topic.py and the Vector(384)
# columns it declares. bge-small-en-v1.5 outputs exactly this, which is why it was chosen.
EMBEDDING_DIM = 384

_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# bge models are trained asymmetrically: a short search query and the longer passage it should
# match are embedded differently, and the query side expects this instruction prefix. Skipping
# it costs real retrieval accuracy, so embed_query applies it and embed_document does not.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None
_model_lock = threading.Lock()


def active_backend() -> str:
    """Which backend is in use — surfaced on /health so a misconfigured deploy is one curl away."""
    return "hash" if os.environ.get("MENTRA_EMBED", "bge").lower() == "hash" else "bge"


def _hash_embed(text: str) -> list[float]:
    """The original placeholder: deterministic, unit-length, and semantically meaningless."""
    seed = int(hashlib.sha256(text.lower().encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec]


def _get_model():
    """Loads the ONNX session once per process, on first use rather than at import.

    Import-time loading would be worse, not better: `import mentra_embed` happens in scripts
    that may never embed anything (init_db.py imports the models package, which is imported by
    seeding and migration paths), and the first load downloads ~130MB. Lazy-but-cached still
    guarantees the "once per process, never per call" property that matters. Double-checked
    locking because FastAPI serves concurrently and two requests can race the first embed.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from fastembed import TextEmbedding

                _model = TextEmbedding(_MODEL_NAME)
    return _model


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed stored content — topic names, transcript chunks, tutor specialties.

    Batched: fastembed amortizes ONNX session overhead across a batch, which matters when
    seeding or ingesting a full caption track.
    """
    if not texts:
        return []
    if active_backend() == "hash":
        return [_hash_embed(t) for t in texts]
    return [vector.tolist() for vector in _get_model().embed(texts)]


def embed_document(text: str) -> list[float]:
    return embed_documents([text])[0]


def embed_query(text: str) -> list[float]:
    """Embed a search query. Applies the bge query prefix; the hash backend ignores it, since
    prefixing a hash input would only make a query fail to match its own document."""
    if active_backend() == "hash":
        return _hash_embed(text)
    return next(iter(_get_model().embed([_QUERY_PREFIX + text]))).tolist()


__all__ = [
    "EMBEDDING_DIM",
    "active_backend",
    "embed_document",
    "embed_documents",
    "embed_query",
]
