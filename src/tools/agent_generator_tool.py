from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import json
import logging
from ..server.registry import Registry

logger = logging.getLogger(__name__)

class AgentGenerationRequest(BaseModel):
    """Request model for generating agents from natural language"""
    description: str = Field(..., description="Natural language description of what the agent should do")
    agent_name: str = Field(..., description="Name for the generated agent")
    tools_needed: Optional[List[str]] = Field(default=[], description="Specific tools the agent should have")
    context: Optional[str] = Field(default="", description="Additional context or constraints")
    deployment_target: Optional[str] = Field(default="local", description="Where to deploy: local, cloud, or specific platform")

class ToolGenerationRequest(BaseModel):
    """Request model for generating tools from natural language"""
    description: str = Field(..., description="Natural language description of what the tool should do")
    tool_name: str = Field(..., description="Name for the generated tool")
    input_schema: Optional[Dict[str, Any]] = Field(default={}, description="Expected input parameters")
    output_format: Optional[str] = Field(default="text", description="Expected output format")

class AgentGeneratorTool(BaseTool):
    """Tool for generating AI agents from natural language descriptions"""
    
    name: str = "Agent Generator"
    description: str = "Generates AI agents and tools from natural language descriptions, deploys them, and makes them executable"
    args_schema: type[BaseModel] = AgentGenerationRequest
    
    def __init__(self, registry: Registry):
        super().__init__()
        # Store data in a way that CrewAI won't interfere with
        object.__setattr__(self, '_registry', registry)
        object.__setattr__(self, '_generated_agents', {})
        object.__setattr__(self, '_generated_tools', {})
    
    @property
    def registry(self) -> Registry:
        """Get the registry instance"""
        return object.__getattribute__(self, '_registry')
    
    @property
    def generated_agents(self) -> Dict[str, Any]:
        """Get the generated agents"""
        return object.__getattribute__(self, '_generated_agents')
    
    @property
    def generated_tools(self) -> Dict[str, Any]:
        """Get the generated tools"""
        return object.__getattribute__(self, '_generated_tools')
    
    def _run(self, description: str, agent_name: str, tools_needed: List[str] = None, 
             context: str = "", deployment_target: str = "local") -> Dict[str, Any]:
        """Generate an agent from natural language description"""
        try:
            logger.info(f"🔧 Generating agent: {agent_name}")
            logger.info(f"📝 Description: {description}")
            
            # Parse the natural language description to extract agent components
            agent_config = self._parse_agent_description(description, agent_name, context)
            
            # Generate or find required tools
            agent_tools = self._resolve_tools(tools_needed or agent_config.get("suggested_tools", []))
            
            # Create the agent workflow
            workflow = self._create_agent_workflow(agent_name, agent_config, agent_tools)
            
            # Register the agent
            agent_id = self.registry.register_agent(workflow)
            
            # Store generation metadata
            self.generated_agents[agent_id] = {
                "name": agent_name,
                "description": description,
                "config": agent_config,
                "tools": agent_tools,
                "deployment_target": deployment_target,
                "status": "deployed"
            }
            
            logger.info(f"✅ Agent {agent_name} generated and deployed with ID: {agent_id}")
            
            return {
                "success": True,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "message": f"Agent '{agent_name}' successfully generated and deployed",
                "usage": f"Use /agent_call?agent_id={agent_id} to execute this agent",
                "tools_available": [tool.get("name", str(tool)) for tool in agent_tools],
                "deployment_status": "deployed",
                "next_steps": [
                    f"Test the agent: POST /agent_call?agent_id={agent_id}",
                    "Monitor execution: GET /executions",
                    "View agent details: GET /agent_list"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate agent {agent_name}: {e}")
            return {
                "success": False,
                "error": f"Failed to generate agent: {str(e)}",
                "agent_name": agent_name
            }
    
    def _parse_agent_description(self, description: str, agent_name: str, context: str) -> Dict[str, Any]:
        """Parse natural language description to extract agent configuration"""
        # This is where you'd integrate with an LLM to parse the description
        # For now, we'll use a rule-based approach that can be enhanced
        
        # Extract role and goal from description
        role = self._extract_role(description, agent_name)
        goal = self._extract_goal(description, context)
        backstory = self._generate_backstory(role, goal)
        
        # Suggest tools based on description
        suggested_tools = self._suggest_tools(description)
        
        return {
            "role": role,
            "goal": goal,
            "backstory": backstory,
            "suggested_tools": suggested_tools,
            "context": context
        }
    
    def _extract_role(self, description: str, agent_name: str) -> str:
        """Extract agent role from description"""
        # Simple role extraction - can be enhanced with LLM
        if "analyze" in description.lower() or "analysis" in description.lower():
            return f"{agent_name} - Data Analysis Specialist"
        elif "trade" in description.lower() or "trading" in description.lower():
            return f"{agent_name} - Trading Expert"
        elif "research" in description.lower() or "investigate" in description.lower():
            return f"{agent_name} - Research Specialist"
        elif "generate" in description.lower() or "create" in description.lower():
            return f"{agent_name} - Content Generator"
        else:
            return f"{agent_name} - AI Assistant"
    
    def _extract_goal(self, description: str, context: str) -> str:
        """Extract agent goal from description"""
        if context:
            return f"{description} in the context of {context}"
        return description
    
    def _generate_backstory(self, role: str, goal: str) -> str:
        """Generate agent backstory"""
        return f"An AI agent specialized in {role.lower()}. {goal} with expertise in relevant domains and tools."
    
    def _suggest_tools(self, description: str) -> List[str]:
        """Suggest tools based on description"""
        tools = []
        desc_lower = description.lower()
        
        # Map common tasks to available tools
        if any(word in desc_lower for word in ["solana", "crypto", "blockchain"]):
            tools.extend(["Solana Trade", "Solana Fetch Price", "Solana Transfer"])
        
        if any(word in desc_lower for word in ["github", "linear", "project"]):
            tools.extend(["GitHub Linear Integration", "Linear Workflow Creator"])
        
        if any(word in desc_lower for word in ["market", "analysis", "research"]):
            tools.extend(["Market Intelligence", "Stock Analysis"])
        
        if any(word in desc_lower for word in ["social", "twitter", "sentiment"]):
            tools.extend(["Reddit Tool", "Social Media Analysis"])
        
        return tools[:5]  # Limit to 5 tools
    
    def _resolve_tools(self, tool_names: List[str]) -> List[Dict[str, Any]]:
        """Resolve tool names to actual tool objects"""
        resolved_tools = []
        
        for tool_name in tool_names:
            try:
                # Search for the tool in the registry
                search_results = self.registry.find_tools(tool_name)
                if search_results:
                    # Use the first matching tool
                    tool_data = search_results[0]
                    resolved_tools.append({
                        "id": tool_data.payload.get("id"),
                        "name": tool_data.payload.get("name", tool_name),
                        "description": tool_data.payload.get("description", ""),
                        "type": "existing",
                        "tool_data": tool_data
                    })
                    logger.info(f"✅ Found tool: {tool_name} -> {tool_data.payload.get('id')}")
                else:
                    # Try to find similar tools
                    similar_tools = self.registry.find_tools(tool_name.split()[0])  # Try first word
                    if similar_tools:
                        tool_data = similar_tools[0]
                        resolved_tools.append({
                            "id": tool_data.payload.get("id"),
                            "name": tool_data.payload.get("name", tool_name),
                            "description": tool_data.payload.get("description", ""),
                            "type": "similar",
                            "tool_data": tool_data,
                            "note": f"Using similar tool for {tool_name}"
                        })
                        logger.info(f"🔄 Using similar tool: {tool_name} -> {tool_data.payload.get('name')}")
                    else:
                        # Create a placeholder for missing tools
                        placeholder_id = f"placeholder_{len(resolved_tools)}"
                        resolved_tools.append({
                            "id": placeholder_id,
                            "name": tool_name,
                            "description": f"Tool for {tool_name} - needs implementation",
                            "type": "placeholder",
                            "note": "This tool needs to be implemented or registered"
                        })
                        logger.warning(f"⚠️ Tool not found: {tool_name} - using placeholder")
            except Exception as e:
                logger.warning(f"⚠️ Could not resolve tool {tool_name}: {e}")
                resolved_tools.append({
                    "id": f"error_{tool_name}",
                    "name": tool_name,
                    "description": f"Error resolving tool: {str(e)}",
                    "type": "error",
                    "note": f"Error during tool resolution: {str(e)}"
                })
        
        return resolved_tools
    
    def _create_agent_workflow(self, agent_name: str, agent_config: Dict[str, Any], 
                              agent_tools: List[Dict[str, Any]]) -> Any:
        """Create a workflow for the generated agent"""
        from ..common.types import Workflow, Agent, Task
        
        # Extract tool IDs for the agent
        tool_ids = [tool["id"] for tool in agent_tools if tool["type"] == "existing"]
        
        # Create the agent
        agent = Agent(
            role=agent_config["role"],
            goal=agent_config["goal"],
            backstory=agent_config["backstory"],
            agent_tools=tool_ids
        )
        
        # Create a default task
        task = Task(
            description=f"Execute: {agent_config['goal']}",
            expected_output="Task execution result",
            agent=agent_name,
            context=[]
        )
        
        # Create the workflow
        workflow = Workflow(
            name=f"Generated: {agent_name}",
            description=agent_config["goal"],
            arguments=["query"],
            agents={agent_name: agent},
            tasks={"execute": task}
        )
        
        return workflow

class ToolGeneratorTool(BaseTool):
    """Tool for generating new tools from natural language descriptions"""
    
    name: str = "Tool Generator"
    description: str = "Generates new tools from natural language descriptions"
    args_schema: type[BaseModel] = ToolGenerationRequest
    
    def __init__(self, registry: Registry):
        super().__init__()
        # Store data in a way that CrewAI won't interfere with
        object.__setattr__(self, '_registry', registry)
    
    @property
    def registry(self) -> Registry:
        """Get the registry instance"""
        return object.__getattribute__(self, '_registry')
    
    def _run(self, description: str, tool_name: str, input_schema: Dict[str, Any] = None, 
             output_format: str = "text") -> Dict[str, Any]:
        """Generate a new tool from natural language description"""
        try:
            logger.info(f"🔧 Generating tool: {tool_name}")
            
            # This would integrate with an LLM to generate actual tool code
            # For now, we'll create a template tool
            
            tool_template = self._generate_tool_template(tool_name, description, input_schema, output_format)
            
            return {
                "success": True,
                "tool_name": tool_name,
                "template": tool_template,
                "message": f"Tool '{tool_name}' template generated",
                "next_steps": [
                    "Review the generated template",
                    "Customize the implementation",
                    "Register the tool with the framework"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate tool {tool_name}: {e}")
            return {
                "success": False,
                "error": f"Failed to generate tool: {str(e)}"
            }
    
    def _generate_tool_template(self, tool_name: str, description: str, 
                               input_schema: Dict[str, Any], output_format: str) -> str:
        """Generate a Python tool template"""
        template = f'''from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any

class {tool_name}Input(BaseModel):
    """Input schema for {tool_name}"""
    # TODO: Define input parameters based on: {input_schema}
    query: str = Field(..., description="Input query for the tool")

class {tool_name}Tool(BaseTool):
    """{description}"""
    
    name: str = "{tool_name}"
    description: str = "{description}"
    args_schema: type[BaseModel] = {tool_name}Input
    
    def _run(self, query: str, **kwargs) -> str:
        """Execute the tool logic"""
        try:
            # TODO: Implement the actual tool logic here
            # This is where you'd add the specific functionality
            
            # Placeholder implementation
            result = f"Tool {tool_name} executed with query: {{query}}"
            
            return result
            
        except Exception as e:
            return f"Error executing {tool_name}: {{str(e)}}"

# Usage:
# tool = {tool_name}Tool()
# result = tool._run(query="your query here")
'''
        return template

def get_agent_generator_tool(registry: Registry) -> AgentGeneratorTool:
    """Get an instance of the agent generator tool"""
    return AgentGeneratorTool(registry=registry)

def get_tool_generator_tool(registry: Registry) -> ToolGeneratorTool:
    """Get an instance of the tool generator tool"""
    return ToolGeneratorTool(registry=registry)
