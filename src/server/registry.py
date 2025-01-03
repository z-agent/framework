from typing import Type
from crewai.tools import BaseTool
from dataclasses import dataclass


@dataclass
class RemoteTool:
    class_tool_id: str

    tool_id: str
    description: str
    model_dict: dict


class ToolRegistry:
    self.tools = {}

    def register_tool(tool_id: str, tool: BaseTool):
        if tool_id in self.tools:
            raise ValueError(f"{tool_id} already in tools")

        self.tools[tool_id] = (
            tool,
            RemoteTool(
                class_tool_id=tool_id,
                tool_id=tool.tool_id,
                description=tool.description,
                model_dict=tool.args_schema.model_json_schema(),
            ),
        )

    def get_tool(tool_id: str):
        return TOOLS[tool_id][1]

    def execute_tool(tool_id, kwargs: dict):
        return TOOLS[tool_id][0].run(**kwargs)
