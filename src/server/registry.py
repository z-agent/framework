from crewai.tools import BaseTool
import yaml
from sentence_transformers import SentenceTransformer
import asyncio
from dataclasses import asdict
import json
import logging
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

from typing import Any, Dict, List, Optional
from crewai.memory.storage.rag_storage import RAGStorage
from crewai.memory.entity.entity_memory import EntityMemory
from crewai.memory.short_term.short_term_memory import ShortTermMemory

AGENTS_COLLECTION = "agents"
TOOLS_COLLECTION = "tools"

logger = logging.getLogger(__name__)

class QdrantStorage(RAGStorage):
    def __init__(self, type, allow_reset=True, embedder_config=None, crew=None):
        super().__init__(type, allow_reset, embedder_config, crew)

    def search(
        self,
        query: str,
        limit: int = 3,
        filter: Optional[dict] = None,
        score_threshold: float = 0,
    ) -> List[Any]:
        points = self.client.query(
            self.type,
            query_text=query,
            query_filter=filter,
            limit=limit,
            score_threshold=score_threshold,
        )
        results = [
            {
                "id": point.id,
                "metadata": point.metadata,
                "context": point.document,
                "score": point.score,
            }
            for point in points
        ]

        return results

    def reset(self) -> None:
        self.client.delete_collection(self.type)

    def _initialize_app(self):
        # Allow cloud URL/API key via env; fallback to default local client
        qdrant_url = os.getenv("QDRANT_URL") or os.getenv("QDRANT_HOST")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        if qdrant_url:
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, check_compatibility=False)
        else:
            self.client = QdrantClient(prefer_grpc=False, timeout=30.0, check_compatibility=False)
        if not self.client.collection_exists(self.type):
            self.client.create_collection(
                collection_name=self.type,
                vectors_config=self.client.get_fastembed_vector_params(),
                sparse_vectors_config=self.client.get_fastembed_sparse_vector_params(),
            )

    def save(self, value: Any, metadata: Dict[str, Any]) -> None:
        # Store memory entry; metadata is optional
        self.client.add(self.type, documents=[value], metadata=[metadata or {}])

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
    def __init__(self, qdrant_client: QdrantClient):
        if not qdrant_client.collection_exists(AGENTS_COLLECTION):
            qdrant_client.create_collection(
                collection_name=AGENTS_COLLECTION,
                vectors_config=VectorParams(
                    size=1536, distance=Distance.COSINE
                ),
            )

        if not qdrant_client.collection_exists(TOOLS_COLLECTION):
            qdrant_client.create_collection(
                collection_name=TOOLS_COLLECTION,
                vectors_config=VectorParams(
                    size=1536, distance=Distance.COSINE
                ),
            )

        self.qdrant_client = qdrant_client
        # Local embeddings to avoid external API issues; pad to 1536 dims
        self.model = SentenceTransformer("all-mpnet-base-v2")
        self.vector_size = 1536
        self.tools = {}
        self.tool_ids = {}  # Mapping from tool ID to UUID
        self.handlers = {
            MessageType.AGENT_METADATA: self.handle_agent_metadata,
            MessageType.AGENT_EXECUTE: self.handle_agent_execute,
        }

    def create_virtual_tools(self, tools: list[str]):
        virtual_tools = []
        for tool_id in tools:
            if tool_id in self.tools:
                tool_instance, tool_info = self.tools[tool_id]
                tool_name = getattr(tool_instance, "name", tool_id)
                tool_description = getattr(tool_instance, "description", f"Tool: {tool_name}")
                base_schema = getattr(tool_instance, 'args_schema', None)
                
                def create_tool_executor(tid):
                    def executor(**kwargs):
                        return self.execute_tool(tid, kwargs)
                    return executor
                
                virtual_tool = create_virtual_tool(
                    tool_name,
                    tool_description,
                    create_tool_executor(tool_id),
                    base_args_schema=base_schema,
                )
                virtual_tools.append(virtual_tool)
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

        # Build a safe task graph: only keep dependencies that are valid task names
        safe_graph = {}
        for task_name, task_cfg in workflow.tasks.items():
            deps = [dep for dep in task_cfg.context if dep in workflow.tasks]
            safe_graph[task_name] = deps

        tasks = {}
        for task in tsort(safe_graph):
            config = workflow.tasks[task]
            tasks[task] = Task(
                description=config.description,
                expected_output=config.expected_output,
                agent=agents[config.agent],
                context=[tasks[dep] for dep in safe_graph[task]],
            )

        return Crew(
            agents=agents.values(),
            tasks=tasks.values(),
            process=Process.sequential,
            memory=True,
            entity_memory=EntityMemory(storage=QdrantStorage("entity")),
            short_term_memory=ShortTermMemory(storage=QdrantStorage("short-term")),
        )

    def register_tool(self, tool_id: str, tool: BaseTool):
        if tool_id in self.tool_ids:
            raise ValueError(f"{tool_id} already in tools")

        tool_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, tool_id + tool.description))

        vector = self._embed_text(tool_id + "\n" + tool.description)
        self.qdrant_client.upsert(
            collection_name=TOOLS_COLLECTION,
            points=[
                {
                    "id": tool_uuid,
                    "vector": vector,
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
        self.tool_ids[tool_id] = tool_uuid

        return tool_uuid

    def find_tools(self, query: str):
        return self.qdrant_client.search(
            collection_name=TOOLS_COLLECTION,
            query_vector=self._embed_text(query),
            limit=5,
        )

    def list_tools(self):
        """Return all tools points with payload for API listing."""
        try:
            tools = self.qdrant_client.scroll(
                collection_name=TOOLS_COLLECTION,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            if tools and len(tools) > 0:
                return tools[0]
            return []
        except Exception as e:
            logger.error(f"Error fetching tools from Qdrant: {e}")
            return []

    def execute_tool(self, tool_id, kwargs: dict):
        tool_instance = self.tools[tool_id][0]
        # Normalize inputs that might arrive as a single JSON string (from LLM actions)
        try:
            if isinstance(kwargs, dict) and len(kwargs) == 1:
                only_key = next(iter(kwargs.keys()))
                only_val = kwargs[only_key]
                if isinstance(only_val, str):
                    import json as _json
                    try:
                        parsed = _json.loads(only_val)
                        if isinstance(parsed, dict):
                            kwargs = parsed
                    except Exception:
                        pass
        except Exception:
            pass

        # Filter kwargs to match tool's args_schema to avoid unexpected params (e.g., 'query')
        try:
            schema = getattr(tool_instance, 'args_schema', None)
            if schema:
                # Pydantic v1/v2 compatibility
                field_names = None
                if hasattr(schema, '__fields__'):
                    field_names = set(schema.__fields__.keys())  # pydantic v1
                elif hasattr(schema, 'model_fields'):
                    field_names = set(schema.model_fields.keys())  # pydantic v2
                if field_names is not None:
                    filtered = {k: v for k, v in (kwargs or {}).items() if k in field_names}
                else:
                    filtered = kwargs or {}
            else:
                filtered = kwargs or {}
        except Exception:
            filtered = kwargs or {}
        return tool_instance.run(**filtered)

    def register_agent(self, workflow: Workflow):
        # Perform a few validations
        agents_list = []
        for agent_name, agent_obj in workflow.agents.items():
            agents_list.append(agent_name)
            # Ensure that we only refer to tools that exist
            for tool in agent_obj.agent_tools:
                if tool not in self.tools:
                    try:
                        # Replace tool ID with UUID
                        agent_obj.agent_tools[agent_obj.agent_tools.index(tool)] = self.tool_ids[tool]
                    except KeyError:
                        raise ValueError(f"tool {tool} does not exist")

        for task in workflow.tasks.values():
            if task.agent not in agents_list:
                raise ValueError(f"agent {task.agent} not defined")

        agent_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, workflow.name + workflow.description))

        vector = self._embed_text(workflow.name + "\n" + workflow.description)
        self.qdrant_client.upsert(
            collection_name=AGENTS_COLLECTION,
            points=[
                {
                    "id": agent_uuid,
                    "vector": vector,
                    "payload": asdict(workflow),
                }
            ],
        )

        return agent_uuid

    def find_agents(self, query: str):
        return self.qdrant_client.search(
            collection_name=AGENTS_COLLECTION,
            query_vector=self._embed_text(query),
            limit=5,
        )

    def list_agents(self):
        """Return all agent points with payload for API listing."""
        try:
            agents = self.qdrant_client.scroll(
                collection_name=AGENTS_COLLECTION,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            if agents and len(agents) > 0:
                return agents[0]
            return []
        except Exception as e:
            logger.error(f"Error fetching agents from Qdrant: {e}")
            return []

    def _embed_text(self, text: str) -> list:
        # Encode and pad/truncate to match Qdrant vector size
        vec = self.model.encode(text)
        if isinstance(vec, list):
            vector = vec
        else:
            vector = list(vec)
        if len(vector) < self.vector_size:
            vector = vector + [0.0] * (self.vector_size - len(vector))
        return vector[:self.vector_size]

    def execute_agent(self, agent_id: str, arguments: dict):
        records = self.qdrant_client.retrieve(
            collection_name=AGENTS_COLLECTION, ids=[agent_id]
        )
        if not records:
            raise ValueError(f"agent {agent_id} not found")
        workflow_record = records[0]
        workflow = from_dict(data_class=Workflow, data=workflow_record.payload)

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
