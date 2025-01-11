import asyncio
from dataclasses import asdict
import json
import crewai_tools
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
import uvicorn

from .registry import ToolRegistry

from ..common.types import (
    MessageType,
    AgentMetadataRequest,
    AgentExecuteRequest,
    AgentExecuteResponse,
    RemoteTool,
    REQUEST_RESPONSE_TYPE_MAP,
)


class AgentRegistry:
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.handlers = {
            MessageType.AGENT_METADATA: self.handle_agent_metadata,
            MessageType.AGENT_EXECUTE: self.handle_agent_execute,
        }

    async def handle_agent_metadata(
        self, data: AgentMetadataRequest
    ) -> RemoteTool:
        return self.tool_registry.get_tool(data.tool_id)

    async def handle_agent_execute(
        self, data: AgentExecuteRequest
    ) -> AgentExecuteResponse:
        return AgentExecuteResponse(
            response=self.tool_registry.execute_tool(
                data.tool.tool_id, data.kwargs
            )
        )

    async def handle(self, message):
        req_type = REQUEST_RESPONSE_TYPE_MAP[message["type"]][0]
        if (handler := self.handlers.get(message["type"])) is not None:
            await websocket.send(
                asdict(await handler(req_type(**message["data"])))
            )


async def main():
    client = QdrantClient(host="localhost", port=6333)

    registry = ToolRegistry(client)
    registry.register_tool("SerperDevTool", crewai_tools.SerperDevTool())

    agent_registry = AgentRegistry(registry)

    uvicorn.run(create_api(agent_registry, registry), host="0.0.0.0", port=8000)

asyncio.run(main())
