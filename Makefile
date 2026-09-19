.PHONY: up down seed backend worker mcp frontend

up:
	docker compose up -d

down:
	docker compose down

seed:
	cd backend && python scripts/init_db.py && python scripts/seed.py

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
