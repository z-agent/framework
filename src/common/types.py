from enum import StrEnum
from dataclasses import dataclass, asdict, field


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


@dataclass
class Task:
    description: str
    expected_output: str
    agent: str
    context: list[str] = field(default_factory=list)


@dataclass
class Workflow:
    name: str
    description: str
    arguments: list[str]  # list of arguments accepted
    agents: dict[str, Agent]
    tasks: dict[str, Task]


REQUEST_RESPONSE_TYPE_MAP = {
    MessageType.AGENT_METADATA: (AgentMetadataRequest, RemoteTool),
    MessageType.AGENT_EXECUTE: (AgentExecuteRequest, AgentExecuteResponse),
}
