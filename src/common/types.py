from enum import StrEnum
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional
from pydantic import BaseModel


class MessageType(StrEnum):
    AGENT_METADATA = "AGENT_METADATA"  # Request agent metadata
    AGENT_EXECUTE = "AGENT_EXECUTE"  # Execute the tool


@dataclass
class AgentMetadataRequest:
    tool_id: str


@dataclass
class RemoteTool:
    class_name: str

    tool_id: str
    description: str
    model_dict: dict


@dataclass
class AgentExecuteRequest:
    tool: RemoteTool
    kwargs: dict


@dataclass
class AgentExecuteResponse:
    response: str


@dataclass
class Agent:
    role: str
    goal: str
    backstory: str
    agent_tools: list[str]

    def dict(self, *args, **kwargs) -> dict:
        """Convert agent to dictionary for serialization"""
        return {
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "agent_tools": self.agent_tools
        }


@dataclass
class Task:
    description: str
    expected_output: str
    agent: str
    context: list[str] = field(default_factory=list)

    def dict(self, *args, **kwargs) -> dict:
        """Convert task to dictionary for serialization"""
        return {
            "description": self.description,
            "expected_output": self.expected_output,
            "agent": self.agent,
            "context": self.context
        }


@dataclass
class Workflow:
    name: str
    description: str
    arguments: list[str]  # list of arguments accepted
    agents: dict[str, Agent]
    tasks: dict[str, Task]

    def dict(self, *args, **kwargs) -> dict:
        """Convert workflow to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
            "agents": {name: agent.dict() for name, agent in self.agents.items()},
            "tasks": {name: task.dict() for name, task in self.tasks.items()}
        }


REQUEST_RESPONSE_TYPE_MAP = {
    MessageType.AGENT_METADATA: (AgentMetadataRequest, RemoteTool),
    MessageType.AGENT_EXECUTE: (AgentExecuteRequest, AgentExecuteResponse),
}
