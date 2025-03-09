import pytest
from unittest.mock import Mock, patch
from src.server.registry import Registry, RegistryError
from qdrant_client import QdrantClient

@pytest.fixture
def mock_qdrant():
    return Mock(spec=QdrantClient)

@pytest.fixture
def registry(mock_qdrant):
    return Registry(mock_qdrant)

def test_register_tool(registry):
    # Test successful tool registration
    tool = Mock()
    registry.register_tool("test_tool", tool)
    assert "test_tool" in registry.tools
    assert registry.tools["test_tool"] == tool

def test_register_duplicate_tool(registry):
    # Test duplicate tool registration
    tool = Mock()
    registry.register_tool("test_tool", tool)
    
    with pytest.raises(RegistryError):
        registry.register_tool("test_tool", tool)

def test_find_tools(registry):
    # Test tool search
    tool1, tool2 = Mock(), Mock()
    registry.register_tool("tool1", tool1)
    registry.register_tool("tool2", tool2)
    
    tools = registry.find_tools("test query")
    assert len(tools) == 2
    assert all(isinstance(tool, dict) for tool in tools)

@pytest.mark.asyncio
async def test_register_agent(registry):
    # Test agent registration
    workflow = {
        "name": "Test Agent",
        "description": "Test description",
        "agents": {},
        "tasks": {}
    }
    
    agent_id = registry.register_agent(workflow)
    assert isinstance(agent_id, str)
    
    # Verify Qdrant interaction
    registry.client.upload_points.assert_called_once() 