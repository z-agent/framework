# AgentHub: A CrewAI-based Framework for Seamless Agent Orchestration

## Overview

AgentHub is built on top of CrewAI that provides a seamless infrastructure for tool discovery, dynamic agent creation, and collaborative workflows. The framework enables developers to focus on building domain-specific tools while the framework handles everything else.

## Core Features

### 1. Semantic Tool Discovery System

AgentHub implements a powerful tool discovery mechanism using vector embeddings and semantic search:

```python
def find_tools(self, query: str):
    return self.qdrant_client.search(
        collection_name=TOOLS_COLLECTION,
        query_vector=self.openai_client.embeddings.create(
            input=query, model=EMBEDDING_MODEL
        )
        .data[0]
        .embedding,
        limit=5,
    )
```

This allows users to find relevant tools using natural language descriptions rather than remembering exact tool names. For example, searching "analyze social sentiment" would find sentiment analysis tools automatically.

### 2. Dynamic Virtual Tool System

The framework dynamically generates tool instances from schemas at runtime:

```python
def create_virtual_tool(remote_tool: RemoteTool, execute):
    class VirtualTool(BaseTool):
        __qualname__ = remote_tool.class_name
        __name__ = remote_tool.class_name
        name: str = remote_tool.class_name
        description: str = remote_tool.description
        args_schema: Type[BaseModel] = create_model_from_json_schema(
            remote_tool.class_name, remote_tool.model_dict
        )
        def _run(self, **kwargs):
            return execute(remote_tool, kwargs)
    return VirtualTool()
```

This eliminates the need to manually create Python classes for every tool, allowing tools to be defined once and used across many agents.

### 3. Declarative Workflow Definition

With AgentHub, you can define complex workflows through a simple JSON API:

```json
{
  "name": "Data Analysis Pipeline",
  "description": "Comprehensive data analysis workflow",
  "arguments": ["dataset", "analysis_type"],
  "agents": {
    "data_processor": {
      "role": "Data Scientist",
      "goal": "Process and clean data for analysis",
      "backstory": "You are an expert data scientist who specializes in preprocessing data.",
      "agent_tools": ["DataCleaningTool", "OutlierDetectionTool"]
    },
    "analyst": {
      "role": "Data Analyst",
      "goal": "Analyze data and extract insights",
      "backstory": "You are a skilled analyst who finds patterns in complex datasets.",
      "agent_tools": ["StatisticalAnalysisTool", "VisualizationTool"]
    }
  },
  "tasks": {
    "data_cleaning": {
      "description": "Clean and preprocess {dataset}",
      "expected_output": "Clean dataset ready for analysis",
      "agent": "data_processor"
    },
    "analysis": {
      "description": "Perform {analysis_type} analysis on the cleaned data",
      "expected_output": "Comprehensive analysis with insights",
      "agent": "analyst",
      "context": ["data_cleaning"]
    }
  }
}
```

### 4. Automatic Task Dependency Resolution

The framework handles complex task dependencies automatically:

```python
tasks = {}
for task in tsort({
    task_name: task.context
    for task_name, task in workflow.tasks.items()
}):
    config = workflow.tasks[task]
    tasks[task] = Task(...)
```

This topological sorting ensures tasks run in the correct order based on their dependencies.

### 5. RESTful API + WebSocket for Real-time Updates

AgentHub provides a complete API for agent management and real-time progress updates:

- `GET /tool_search?query=your_search` - Find tools semantically
- `GET /agent_search?query=your_search` - Find agents semantically
- `POST /save_agent` - Register a new agent workflow
- `POST /agent_call` - Execute an agent with specific inputs
- WebSocket connection for real-time progress updates

## Simplicity: Just Create a Tool

With AgentHub, developers only need to focus on creating tools - everything else is handled by the framework:

1. **Create a CrewAI tool** - Focus on your domain-specific functionality
2. **Register it with the framework** - One line of code adds your tool to the registry

```python
# Example tool creation
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class MyToolSchema(BaseModel):
    input_parameter: str = Field(..., description="Description of parameter")
    optional_param: int = Field(10, description="Optional parameter with default")

class MyCustomTool(BaseTool):
    name: str = "My custom analysis tool"
    description: str = "A tool that performs custom analysis"
    args_schema: Type[BaseModel] = MyToolSchema
    
    def _run(self, **kwargs):
        # Your domain-specific logic here
        return {"result": "Analysis completed"}

# Register with just one line
registry.register_tool("MyCustomTool", MyCustomTool())
```

## What AgentHub Handles For You

Once you create a tool, AgentHub takes care of:

1. **Tool Registry and Discovery** - Storage, indexing, and semantic search
2. **Schema Management** - Translation between JSON and Pydantic models
3. **Virtual Tool Creation** - Dynamic proxy generation for registered tools
4. **Agent Configuration** - Declarative agent definition and instantiation
5. **Task Orchestration** - Dependency resolution and execution order
6. **Progress Tracking** - Real-time updates during execution
7. **API Interfaces** - RESTful endpoints and WebSocket connections

## Example: Market Intelligence Tool

Here's a complete example showing how easy it is to create a market intelligence tool for AgentHub:

```python
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class MindshareSchema(BaseModel):
    token_symbol: str = Field(..., description="Name of token for analysis")
    days_back: int = Field(7, description="Days of historical data to analyze")

class MindshareTool(BaseTool):
    name: str = "Analyze token mindshare and social metrics"
    description: str = "A tool to analyze social sentiment and engagement metrics for tokens"
    args_schema: Type[BaseModel] = MindshareSchema
    
    def __init__(self, mongodb_uri=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mongodb_uri = mongodb_uri or os.environ.get("MONGODB_URI")
    
    def _run(self, **kwargs):
        token_symbol = kwargs["token_symbol"]
        days_back = kwargs["days_back"]
        
        # Your implementation to fetch and analyze mindshare data
        # This could query a database, API, or other data source
        
        # Return structured analysis results
        return {
            "mention_velocity": 237.5,
            "engagement_ratio": 0.82,
            "sentiment_score": 0.35,
            # Other metrics...
        }
```

With just this code, your tool becomes available to all agents in the system. Users can discover it through semantic search, incorporate it into workflows, and receive results through the API - all without writing any additional code.

## Getting Started

1. **Install AgentHub**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server**:
   ```bash
   python -m src.server.main
   ```

3. **Create a tool**:
   ```python
   # your_tool.py
   from agenthub import register_tool
   from your_module import YourTool
   
   register_tool("YourToolName", YourTool())
   ```

4. **Use the API** to create and execute agents:
   ```bash
   curl -X POST http://localhost:8000/save_agent -H "Content-Type: application/json" -d '{...}'
   ```

## Summary

AgentHub provides a production-ready infrastructure for agent-based systems, allowing developers to focus on domain-specific tools while the framework handles discovery, orchestration, and API interfaces. This dramatically accelerates development and enables more flexible, powerful agent-based applications.
