from websockets.sync.client import connect
import json
from ..common.types import (
    AgentMetadataRequest,
    REQUEST_RESPONSE_TYPE_MAP,
    MessageType,
)
from dataclasses import asdict


def make_request(websocket, request_type, request):
    req_type, resp_type = REQUEST_RESPONSE_TYPE_MAP[request_type]
    if not isinstance(request, req_type):
        raise ValueError(
            f"Invalid request type {type(request)}, expected {req_type}"
        )
    websocket.send(json.dumps({"type": request_type, "data": asdict(request)}))
    return resp_type(**json.loads(websocket.recv()))


def main():
    with connect("ws://localhost:8000") as websocket:
        tool = make_request(
            websocket,
            MessageType.AGENT_METADATA,
            AgentMetadataRequest(tool_id="TOOL_ID"),
        )
        print(f"Received {tool}")

        virtual_tool = create_virtual_tool(
            tool,
            lambda tool, kwargs: make_request(
                websocket,
                MessageType.AGENT_EXECUTE,
                AgentExecutionRequest(tool=tool, kwargs=kwargs),
            ).response,
        )
        print(virtual_tool)


main()
