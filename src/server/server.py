import asyncio
from websockets.server import serve
from enum import StrEnum
from dataclasses import dataclass, asdict


class MessageType(StrEnum):
    AGENT_METADATA = "AGENT_METADATA"  # Request agent metadata


@dataclass
class AgentMetadataRequest:
    tool_id: str


class AgentRegistry:
    self.handlers = {
        AGENT_METADATA: self.handle_agent_metadata,
    }

    def __init__(tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

    async def handle_agent_metadata(data):
        data = AgentMetadataRequest(**data)
        return asdict(self.tool_registry.get_tool(data.tool_id))

    async def server(self, websocket):
        async for message in websocket:
            if (handler := self.handlers.get(message["type"])) is not None:
                await websocket.send(await handler(message["data"]))


async def main():
    async with serve(AgentRegistry().server, "localhost", 8000):
        await asyncio.get_running_loop().create_future()


asyncio.run(main())
