from typing import Union, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .registry import Registry
from ..common.types import Workflow, Agent, Task


class AgentCallRequest(BaseModel):
    query: str


class AgentConfig(BaseModel):
    role: str
    goal: str
    backstory: str
    agent_tools: list[str]


class TaskConfig(BaseModel):
    description: str
    expected_output: str
    agent: str
    context: list[str] = []


class WorkflowRequest(BaseModel):
    name: str
    description: str
    arguments: list[str]
    agents: Dict[str, AgentConfig]
    tasks: Dict[str, TaskConfig]


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
    def save_agent(workflow_request: WorkflowRequest):
        try:
            # Convert the validated request to a Workflow object
            workflow = Workflow(
                name=workflow_request.name,
                description=workflow_request.description,
                arguments=workflow_request.arguments,
                agents={
                    name: Agent(**agent_config.dict())
                    for name, agent_config in workflow_request.agents.items()
                },
                tasks={
                    name: Task(**task_config.dict())
                    for name, task_config in workflow_request.tasks.items()
                },
            )
            agent_id = registry.register_agent(workflow)
            return {"agent_id": agent_id}
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent_search")
    def agent_search(query: str):
        return registry.find_agents(query)

    @app.post("/agent_call")
    def agent_call(agent_id: str, request: AgentCallRequest):
        try:
            return registry.execute_agent(agent_id, {"query": request.query})
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent_list")
    def agent_list():
        return registry.list_agents()

    return app
