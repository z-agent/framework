from websockets.sync.client import connect
import json
from ..common.types import (
    AgentMetadataRequest,
    REQUEST_RESPONSE_TYPE_MAP,
    MessageType,
)
from dataclasses import asdict
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
import yaml


def read_yaml(config):
    with open(config, "r") as file:
        return yaml.safe_load(file)


def make_request(websocket, request_type, request):
    req_type, resp_type = REQUEST_RESPONSE_TYPE_MAP[request_type]
    if not isinstance(request, req_type):
        raise ValueError(
            f"Invalid request type {type(request)}, expected {req_type}"
        )
    websocket.send(json.dumps({"type": request_type, "data": asdict(request)}))
    return resp_type(**json.loads(websocket.recv()))


def create_virtual_tools(websocket, tools: list[str]):
    virtual_tools = []
    for tool in tools:
        tool = make_request(
            websocket,
            MessageType.AGENT_METADATA,
            AgentMetadataRequest(tool_id=tool),
        )
        virtual_tools.append(
            create_virtual_tool(
                tool,
                lambda tool, kwargs: make_request(
                    websocket,
                    MessageType.AGENT_EXECUTE,
                    AgentExecuteRequest(tool=tool, kwargs=kwargs),
                ).response,
            )
        )


def generate_crew(websocket):
    class GeneratedCrew:
        @crew
        def crew(self) -> Crew:
            return Crew(
                agents=self.agents,
                tasks=self.tasks,
                process=Process.sequential,
                verbose=True,
            )

    agents_config = read_yaml("config/agents.yaml")
    tasks_config = read_yaml("config/tasks.yaml")

    for agent_name, config in agents_config.values():

        @agent
        def fn(self) -> Agent:
            return Agent(
                config=self.agents_config[agent_name],
                verbose=True,
                tools=create_virtual_tools(config.get("tools", [])),
            )

        setattr(GeneratedCrew, agent_name, fn)

    for task_name in tasks_config:

        @task
        def fn(self) -> Task:
            return Task(config=self.tasks_config[task_name])

        setattr(GeneratedCrew, task_name, fn)

    return CrewBase(GeneratedCrew)()


def main():
    with connect("ws://localhost:8000") as websocket:
        generated_crew = generate_crew(websocket)
        generated_crew.crew().kickoff(inputs={"topic": "AI Agents"})


main()
