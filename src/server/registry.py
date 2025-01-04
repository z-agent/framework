from crewai.tools import BaseTool
from ..common.types import RemoteTool


class ToolRegistry:
    tools = {}

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

    def get_tool(self, tool_id: str):
        return self.tools[tool_id][1]

    def execute_tool(self, tool_id, kwargs: dict):
        return self.tools[tool_id][0].run(**kwargs)
