.PHONY: up down install-shared seed reembed test test-extension backend worker mcp frontend extension extension-watch

up:
	docker compose up -d

down:
	docker compose down

# The shared embedder is an editable install rather than a copied module, so the backend, the
# seed script and both MCP servers load one ONNX session config instead of four drifting copies.
# Run once per virtualenv.
install-shared:
	pip install -e ./shared

seed:
	cd backend && python scripts/init_db.py && python scripts/seed.py

# Rewrites every stored vector with the current embedder. Needed after changing MENTRA_EMBED
# or the model behind it — vectors from different embedders are not comparable, and mixing them
# degrades ranking silently rather than erroring.
reembed:
	cd backend && python scripts/reembed.py

test:
	cd backend && python -m pytest

test-extension:
	cd extension && npm test

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

worker:
	cd backend && celery -A app.celery_app worker --loglevel=info

mcp:
	cd mcp_servers/video_transcript && python server.py & \
	cd mcp_servers/tutor_match && python server.py & \
	cd mcp_servers/calendar_booking && python server.py & \
	cd mcp_servers/maps_places && python server.py & \
	wait

frontend:
	cd frontend && npm run dev

# Builds extension/dist, which is what you point "Load unpacked" at in chrome://extensions.
extension:
	cd extension && npm install && npm run build

extension-watch:
	cd extension && npm run watch
