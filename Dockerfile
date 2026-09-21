# Backend deploy image: API + Celery worker + the four MCP servers in one container,
# launched by deploy/start.sh. The frontend deploys separately (Vercel).
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
# backend/requirements.txt already covers the MCP servers' deps (mcp, asyncpg, dotenv).
RUN pip install --no-cache-dir -r backend/requirements.txt

# The shared embedder is a package, not a vendored file: app/main.py and both vector MCP
# servers import parallax_embed at module load, so leaving it out builds a green image that
# crash-loops on boot. Installed before the app code so the layer survives ordinary edits.
COPY shared shared
RUN pip install --no-cache-dir -e ./shared

# Bake the ONNX weights into the image. Without this the first embed of every fresh machine
# downloads ~130MB from HuggingFace: it makes the first demo query slow, and it turns a
# HuggingFace outage into a boot failure. Baked, the model is on disk before the app starts.
ENV FASTEMBED_CACHE_PATH=/opt/fastembed
RUN python -c "from parallax_embed import embed_document; embed_document('warm the cache')"

COPY backend backend
COPY mcp_servers mcp_servers
COPY deploy/start.sh start.sh
RUN chmod +x start.sh

ENV PYTHONUNBUFFERED=1

CMD ["./start.sh"]
