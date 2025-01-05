import asyncio
from websockets.server import serve
from dataclasses import asdict
import json
import crewai_tools

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

    async def server(self, websocket):
        async for message in websocket:
            message = json.loads(message)
            req_type = REQUEST_RESPONSE_TYPE_MAP[message["type"]][0]
            if (handler := self.handlers.get(message["type"])) is not None:
                await websocket.send(
                    asdict(await handler(req_type(**message["data"])))
                )


async def main():
    registry = ToolRegistry()
    registry.register_tool("SerperDevTool", crewai_tools.SerperDevTool())

    async with serve(AgentRegistry(registry).server, "localhost", 8000):
        await asyncio.get_running_loop().create_future()


asyncio.run(main())
