from typing import Type
from crewai.tools import BaseTool
from dataclasses import dataclass

TOOLS = {}


@dataclass
class RemoteTool:
    class_name: str

    name: str
    description: str
    model_dict: dict


def register_tool(name: str, tool: BaseTool):
    if name in TOOLS:
        raise ValueError(f"{name} already in tools")

    TOOLS[name] = (
        tool,
        RemoteTool(
            class_name=name,
            name=tool.name,
            description=tool.description,
            model_dict=tool.args_schema.model_json_schema(),
        ),
    )


def get_tool(name: str):
    return TOOLS[name][1]


def execute_tool(name, kwargs: dict):
    return TOOLS[name][0].run(**kwargs)
