import crewai_tools
import uvicorn
from qdrant_client import QdrantClient

from .api import create_api
from .registry import Registry


def main():
    client = QdrantClient(host="localhost", port=6333)

    registry = Registry(client)

    # TODO this will be made dynamic in the future where tools will be
    # run as their own services
    registry.register_tool("SerperDevTool", crewai_tools.SerperDevTool())

    uvicorn.run(create_api(registry), host="0.0.0.0", port=8000)


main()
