from crewai.tools import BaseTool
from ..common.types import RemoteTool
from sentence_transformers import SentenceTransformer

TOOLS_COLLECTION = "tools"


class ToolRegistry:
    tools = {}

    def __init__(self, qdrant_client):
        if not qdrant_client.collection_exists(TOOLS_COLLECTION):
            qdrant_client.create_collection(
                collection_name=TOOLS_COLLECTION,
                vector_config=VectorParams(size=100, distance=Distance.COSINE),
            )
        self.qdrant_client = qdrant_client
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def register_tool(self, tool_id: str, tool: BaseTool):
        if tool_id in self.tools:
            raise ValueError(f"{tool_id} already in tools")

        self.qdrant_client.upsert(
            collection_name=TOOLS_COLLECTION,
            points={
                "id": tool_id,
                "vector": self.model.encode(tool_id + "\n" + tool.description),
                "payload": {
                    "id": tool_id,
                    "description": tool.description,
                },
            },
        )

        self.tools[tool_id] = (
            tool,
            RemoteTool(
                class_tool_id=tool_id,
                tool_id=tool_id,
                description=tool.description,
                model_dict=tool.args_schema.model_json_schema(),
            ),
        )

    def find_tools(self, query: str):
        return self.qdrant_client.search(
            collection_name=TOOLS_COLLECTION,
            query_vector=model.encode(query).tolist(),
            limit=5,
        )

    def get_tool(self, tool_id: str):
        return self.tools[tool_id][1]

    def execute_tool(self, tool_id, kwargs: dict):
        return self.tools[tool_id][0].run(**kwargs)
