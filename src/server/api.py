from typing import Union
from fastapi import FastAPI
from .registry import ToolRegistry

def create_api(agent_registry, tool_registry: ToolRegistry):
    app = FastAPI()

    @app.websocket("/agent_ws")
    async def agent_proxy(websocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_json()
            await websocket.send_json(agent_registry.handle(data))

    @app.get("/tool_search")
    def tool_search(query: str):
        return tool_registry.find_tools(query)

    @app.post("/save_agent")
    def save_agent():
        pass

    return app
