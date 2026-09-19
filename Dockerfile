# Backend deploy image: API + Celery worker + the four MCP servers in one container,
# launched by deploy/start.sh. The frontend deploys separately (Vercel).
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
# backend/requirements.txt already covers the MCP servers' deps (mcp, asyncpg, dotenv).
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY mcp_servers mcp_servers
COPY deploy/start.sh start.sh
RUN chmod +x start.sh

ENV PYTHONUNBUFFERED=1

CMD ["./start.sh"]
