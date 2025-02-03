from crewai.tools import BaseTool
import yaml
from sentence_transformers import SentenceTransformer
import asyncio
from dataclasses import asdict
import json
import crewai_tools
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
import uvicorn
from ..common.types import (
    MessageType,
    AgentMetadataRequest,
    AgentExecuteRequest,
    AgentExecuteResponse,
    RemoteTool,
    REQUEST_RESPONSE_TYPE_MAP,
    Workflow,
)
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from dacite import from_dict
import threading
import os
from .virtual_tool import create_virtual_tool
from .util import tsort

AGENTS_COLLECTION = "agents"
TOOLS_COLLECTION = "tools"


def generate_agent_fn(agent_name, tools):
    @agent
    def fn(self) -> Agent:
        return Agent(
            config=self.agents_config[agent_name], tools=tools, verbose=True
        )

    return fn


def generate_task_fn(task_name):
    @task
    def fn(self) -> Task:
        return Task(config=self.tasks_config[task_name])

    return fn


class Registry:
    def __init__(self, qdrant_client):
        try:
            qdrant_client.delete_collection(AGENTS_COLLECTION)
        except Exception:
            pass

        try:
            qdrant_client.delete_collection(TOOLS_COLLECTION)
        except Exception:
            pass

        if not qdrant_client.collection_exists(AGENTS_COLLECTION):
            qdrant_client.create_collection(
                collection_name=AGENTS_COLLECTION,
                vectors_config=VectorParams(
                    size=384, distance=Distance.COSINE
                ),
            )
        if not qdrant_client.collection_exists(TOOLS_COLLECTION):
            qdrant_client.create_collection(
                collection_name=TOOLS_COLLECTION,
                vectors_config=VectorParams(
                    size=384, distance=Distance.COSINE
                ),
            )
        self.qdrant_client = qdrant_client
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.tools = {}
        self.handlers = {
            MessageType.AGENT_METADATA: self.handle_agent_metadata,
            MessageType.AGENT_EXECUTE: self.handle_agent_execute,
        }

    def create_virtual_tools(self, tools: list[str]):
        virtual_tools = []
        for tool in tools:
            virtual_tools.append(
                create_virtual_tool(
                    self.tools[tool][1],
                    lambda tool, kwargs: self.execute_tool(
                        tool.tool_id, kwargs
                    ),
                )
            )
        return virtual_tools

    def generate_crew(self, workflow: Workflow):
        agents = {}
        for agent, config in workflow.agents.items():
            agents[agent] = Agent(
                role=config.role,
                goal=config.goal,
                backstory=config.backstory,
                tools=self.create_virtual_tools(config.agent_tools),
                verbose=True,
            )

        tasks = {}
        for task in tsort(
            {
                task_name: task.context
                for task_name, task in workflow.tasks.items()
            }
        ):
            config = workflow.tasks[task]
            tasks[task] = Task(
                description=config.description,
                expected_output=config.expected_output,
                agent=agents[config.agent],
                context=[tasks[task] for task in config.context],
            )

        return Crew(
            agents=agents.values(),
            tasks=tasks.values(),
            process=Process.sequential,
        )

    def register_tool(self, tool_id: str, tool: BaseTool):
        if tool_id in self.tools:
            raise ValueError(f"{tool_id} already in tools")

        tool_uuid = str(uuid.uuid4())

        self.qdrant_client.upsert(
            collection_name=TOOLS_COLLECTION,
            points=[
                {
                    "id": tool_uuid,
                    "vector": self.model.encode(
                        tool_id + "\n" + tool.description
                    ),
                    "payload": {
                        "id": tool_id,
                        "description": tool.description,
                    },
                }
            ],
        )

        self.tools[tool_uuid] = (
            tool,
            RemoteTool(
                class_name=tool_id,
                tool_id=tool_uuid,
                description=tool.description,
                model_dict=tool.args_schema.model_json_schema(),
            ),
        )

        return tool_uuid

    def find_tools(self, query: str):
        return self.qdrant_client.search(
            collection_name=TOOLS_COLLECTION,
            query_vector=self.model.encode(query).tolist(),
            limit=5,
        )

    def execute_tool(self, tool_id, kwargs: dict):
        return self.tools[tool_id][0].run(**kwargs)

    def register_agent(self, workflow: Workflow):
        # Perform a few validations
        agents_list = []
        for agent_name, agent_obj in workflow.agents.items():
            agents_list.append(agent_name)
            # Ensure that we only refer to tools that exist
            for tool in agent_obj.agent_tools:
                if tool not in self.tools:
                    raise ValueError(f"tool {tool} does not exist")

        for task in workflow.tasks.values():
            if task.agent not in agents_list:
                raise ValueError(f"agent {task.agent} not defined")

        agent_uuid = str(uuid.uuid4())

        self.qdrant_client.upsert(
            collection_name=AGENTS_COLLECTION,
            points=[
                {
                    "id": agent_uuid,
                    "vector": self.model.encode(
                        workflow.name + "\n" + workflow.description
                    ),
                    "payload": asdict(workflow),
                }
            ],
        )

        return agent_uuid

    def find_agents(self, query: str):
        return self.qdrant_client.search(
            collection_name=AGENTS_COLLECTION,
            query_vector=self.model.encode(query).tolist(),
            limit=5,
        )

    def execute_agent(self, agent_id: str, arguments: dict):
        workflow = self.qdrant_client.retrieve(
            collection_name=AGENTS_COLLECTION, ids=[agent_id]
        )[0]
        workflow = from_dict(data_class=Workflow, data=workflow.payload)

        for argument in arguments.keys():
            if argument not in workflow.arguments:
                raise ValueError(
                    f"invalid argument {argument}, valid: {workflow.arguments}"
                )

        return self.generate_crew(workflow).kickoff(inputs=arguments)

    async def handle_agent_metadata(
        self, data: AgentMetadataRequest
    ) -> RemoteTool:
        return self.tools[data.tool_id][1]

    async def handle_agent_execute(
        self, data: AgentExecuteRequest
    ) -> AgentExecuteResponse:
        return AgentExecuteResponse(
            response=self.execute_tool(data.tool.tool_id, data.kwargs)
        )

    async def handle(self, message):
        req_type = REQUEST_RESPONSE_TYPE_MAP[message["type"]][0]
        if (handler := self.handlers.get(message["type"])) is not None:
            return asdict(await handler(req_type(**message["data"])))
