from websockets.sync.client import connect
import json


def main():
    with connect("ws://localhost:8000") as websocket:
        websocket.send(
            json.dumps(
                {"type": "AGENT_METADATA", "data": {"tool_id": "TOOL_ID"}}
            )
        )
        print(f"Received {websocket.recv()}")


main()
