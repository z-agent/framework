from enum import StrEnum
from dataclasses import dataclass, asdict


class MessageType(StrEnum):
    AGENT_METADATA = "AGENT_METADATA"  # Request agent metadata
    AGENT_EXECUTE = "AGENT_EXECUTE"  # Execute the tool


@dataclass
class AgentMetadataRequest:
    tool_id: str


@dataclass
class RemoteTool:
    class_tool_id: str

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


REQUEST_RESPONSE_TYPE_MAP = {
    MessageType.AGENT_METADATA: (AgentMetadataRequest, RemoteTool),
    MessageType.AGENT_EXECUTE: (AgentExecuteRequest, AgentExecuteResponse),
}
