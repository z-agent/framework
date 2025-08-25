from typing import Type, Any, Dict, Optional
import logging
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, create_model
from src.common.types import RemoteTool

logger = logging.getLogger(__name__)

def create_virtual_tool(tool_name: str, tool_description: str, tool_function, base_args_schema: Optional[Type[BaseModel]] = None) -> BaseTool:
    # Prefer the base tool's args schema when provided (exact signature)
    if base_args_schema is not None:
        tool_args_schema = base_args_schema
    elif "Reddit" in tool_name or "reddit" in tool_description.lower():
        class RedditToolSchema(BaseModel):
            subreddit: str = Field(default="startups", description="Subreddit name (without r/ prefix)")
            time_filter: str = Field(default="month", description="Time filter: hour, day, week, month, year, all")
            limit: int = Field(default=5, description="Number of posts to fetch (1-25)")
            sort_by: str = Field(default="top", description="Sort by: hot, new, top, rising")
        tool_args_schema = RedditToolSchema
    elif "SaaS" in tool_name or "business" in tool_description.lower():
        class SaaSToolSchema(BaseModel):
            market_data: str = Field(default="", description="Market research data, pain points, or audience insights from previous analysis")
            target_audience: str = Field(default="general", description="Target audience or market segment")
            complexity_level: str = Field(default="mvp", description="Complexity level: mvp, intermediate, advanced")
            query: str = Field(default="", description="Alternative input if market_data is not available")
        tool_args_schema = SaaSToolSchema
    elif "WebSearch" in tool_name or "search" in tool_description.lower() or "serper" in tool_description.lower():
        # WebSearch tool expects search_query parameter
        class WebSearchToolSchema(BaseModel):
            search_query: str = Field(description="Mandatory search query you want to use to search the internet")
        tool_args_schema = WebSearchToolSchema
    else:
        # Generic schema for other tools
        class GenericToolSchema(BaseModel):
            query: str = Field(default="", description="Input query or request")
        tool_args_schema = GenericToolSchema

    class VirtualTool(BaseTool):
        __qualname__ = tool_name
        __name__ = tool_name

        name: str = tool_name
        description: str = tool_description
        args_schema: type = tool_args_schema
        
        def _run(self, **kwargs):
            # Prevent empty parameter calls that cause infinite loops
            if not kwargs or kwargs == {}:
                error_msg = f"❌ REJECTED: {tool_name} called with empty parameters. This causes infinite loops."
                if "Reddit" in tool_name:
                    error_msg += " Use: {'subreddit': 'startups', 'time_filter': 'month', 'limit': 5, 'sort_by': 'top'}"
                elif "SaaS" in tool_name:
                    error_msg += " Use: {'market_data': 'market trends', 'query': 'generate business plan'}"
                else:
                    error_msg += " Use: {'query': 'your specific request'}"
                
                logger.warning(error_msg)
                return {
                    "error": error_msg,
                    "success": False,
                    "loop_detected": True,
                    "tool_name": tool_name
                }
            
            # Log tool execution to monitor
            try:
                from .execution_monitor import execution_monitor
                # Find the current execution for this tool
                for exec_id, exec_data in execution_monitor.active_executions.items():
                    if exec_data['status'] == 'running':
                        execution_monitor.log_tool_execution(exec_id, tool_name, kwargs, "Executing...")
                        break
                
                # Execute the tool
                result = tool_function(**kwargs)
                
                # Log completion
                for exec_id, exec_data in execution_monitor.active_executions.items():
                    if exec_data['status'] == 'running':
                        execution_monitor.log_tool_execution(exec_id, tool_name, kwargs, result)
                        break
                
                return result
            except Exception as e:
                # Log error
                for exec_id, exec_data in execution_monitor.active_executions.items():
                    if exec_data['status'] == 'running':
                        execution_monitor.log_tool_execution(exec_id, tool_name, kwargs, f"ERROR: {str(e)}")
                        break
                
                error_result = {
                    "error": f"Tool execution failed: {str(e)}",
                    "tool_name": tool_name,
                    "success": False
                }
                return error_result

    return VirtualTool()
