import crewai_tools
import uvicorn
from qdrant_client import QdrantClient

from .api import create_api
from .registry import Registry
from ..tools.agentipy_tools import gen_tools
from ..tools.stock import (
    FundamentalAnalysis,
    TechnicalAnalysis,
    RiskAssessment,
)


def main():
    client = QdrantClient(host="localhost", port=6333)

    registry = Registry(client)

    # TODO this will be made dynamic in the future where tools will be
    # run as their own services
    registry.register_tool("SerperDevTool", crewai_tools.SerperDevTool())
    registry.register_tool("FundamentalAnalysis", FundamentalAnalysis())
    registry.register_tool("TechnicalAnalysis", TechnicalAnalysis())
    registry.register_tool("RiskAssessment", RiskAssessment())
    for tool_name, tool in gen_tools():
        registry.register_tool(tool_name, tool)

    uvicorn.run(create_api(registry), host="0.0.0.0", port=8000)


main()
