import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.realtime import channel_name

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def learning_session_ws(websocket: WebSocket, session_id: str):
    """Streams every LearningState update to the browser as each LangGraph node completes
    (Section 10). The same pattern would carry peer feed updates on a per-user channel.
    """
    await websocket.accept()
    r = redis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel_name(session_id))

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"].decode())
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel_name(session_id))
        await pubsub.aclose()
        await r.aclose()
