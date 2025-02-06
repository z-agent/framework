from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .registry import Registry
from ..common.types import Workflow


def create_api(registry: Registry):
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.websocket("/agent_ws")
    async def agent_proxy(websocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_json()
            await websocket.send_json(registry.handle(data))

    @app.get("/tool_search")
    def tool_search(query: str):
        return registry.find_tools(query)

    @app.post("/save_agent")
    def save_agent(workflow: Workflow):
        agent_id = registry.register_agent(workflow)
        return {"agent_id": agent_id}

    @app.get("/agent_search")
    def agent_search(query: str):
        return registry.find_agents(query)

    @app.get("/agent_call")
    def agent_call(agent_id: str, arguments: dict):
        # arguments are validated dynamically based on the schema stored in the
        # database
        return registry.execute_agent(agent_id, arguments)

    return app
