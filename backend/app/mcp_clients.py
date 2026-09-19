"""Thin MCP client wrappers. Orchestrator nodes call these instead of touching video/tutor/
calendar/maps data directly — the whole point of the MCP layer (Section 5) is that agents
never talk to the outside world except through a tool call whose result is returned here.
"""

import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings


async def call_mcp_tool(url: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            # FastMCP emits one TextContent block per list item for list-returning tools
            # (rather than one block holding the whole JSON array), so content[0].text alone
            # is not the full result. structuredContent is the reliable source: per the MCP
            # spec it wraps non-object return types (e.g. a bare list) under a "result" key,
            # since structured content must be a JSON object at the top level.
            if result.structuredContent is not None:
                data = result.structuredContent
                if isinstance(data, dict) and set(data.keys()) == {"result"}:
                    return data["result"]
                return data

            text = result.content[0].text if result.content else "null"
            return json.loads(text)


async def search_transcripts(topic_query: str, difficulty_level: str = "intro", max_results: int = 5):
    return await call_mcp_tool(
        settings.video_mcp_url,
        "search_transcripts",
        {"topic_query": topic_query, "difficulty_level": difficulty_level, "max_results": max_results},
    )


async def find_tutors(subject: str, topic_query: str, **filters):
    return await call_mcp_tool(
        settings.tutor_mcp_url, "find_tutors", {"subject": subject, "topic_query": topic_query, **filters}
    )


async def get_availability(tutor_id: str, week: str):
    return await call_mcp_tool(settings.calendar_mcp_url, "get_availability", {"tutor_id": tutor_id, "week": week})


async def create_booking_hold(tutor_id: str, learner_id: str, slot: str):
    return await call_mcp_tool(
        settings.calendar_mcp_url,
        "create_booking_hold",
        {"tutor_id": tutor_id, "learner_id": learner_id, "slot": slot},
    )


async def nearby_tutors(lat: float, lng: float, radius_km: float):
    return await call_mcp_tool(
        settings.maps_mcp_url, "nearby_tutors", {"lat": lat, "lng": lng, "radius_km": radius_km}
    )
