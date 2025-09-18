#!/usr/bin/env python3
"""
🤖 SCOPE AGENTKIT IDEA AGENT
AI agent that specializes in analyzing business ideas for AgentKit integration
"""

from crewai import Agent, Task, Crew
from typing import Dict, Any, List
import logging
from ..common.types import Workflow

logger = logging.getLogger(__name__)

def create_scope_agkit_idea_agent(scope_tool) -> Agent:
    """Create the Scope AgentKit Idea agent with direct execution"""
    
    # Import the direct tool
    from src.tools.direct_scope_agkit_tool import direct_scope_agkit_tool
    
    return Agent(
        role="AgentKit Integration Specialist",
        goal="Execute the Direct Scope AgentKit Tool with the exact input parameters",
        backstory="""You MUST use the exact query parameter from the input. DO NOT use examples like 'Regulatory Consulting Services for Crypto Firms'. ONLY use the query parameter provided in the task inputs.""",
        tools=[direct_scope_agkit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=1,
        memory=False
    )

def create_scope_agkit_idea_workflow(scope_tool) -> Workflow:
    """Create the complete Scope AgentKit Idea workflow"""
    
    # Create the specialist agent
    agent = create_scope_agkit_idea_agent(scope_tool)
    
    # Define the main analysis task - SIMPLE AND DIRECT
    analysis_task = Task(
        description="""Execute Direct Scope AgentKit Tool using the exact query parameter from inputs. Query parameter: {query}. DO NOT use 'Regulatory Consulting Services for Crypto Firms' or any example text.""",
        agent=agent,
        expected_output="""Raw tool output from Direct Scope AgentKit Tool.""",
        context="""Task inputs contain the query parameter. Use it exactly as provided.""",
        output_file="agentkit_analysis_report.md"
    )
    
    # Create the workflow
    workflow = Workflow(
        name="Scope AgentKit Idea Analysis",
        description="Direct analysis of business ideas for AgentKit integration potential",
        arguments={
            "query": "The business idea to analyze for AgentKit integration",
            "mode": "Analysis mode: builder, investor, or founder (default: builder)",
            "complexity_level": "Expected integration complexity: simple, medium, or advanced (default: medium)",
            "project_id": "Optional project identifier for tracking"
        },
        agents={"agentkit_specialist": agent},
        tasks={"analyze_idea": analysis_task}
    )
    
    return workflow

def scope_agkit_idea_direct(query: str, mode: str = "builder", complexity_level: str = "medium", project_id: str = None) -> Dict[str, Any]:
    """Direct function to scope AgentKit idea without agent overhead - most efficient approach"""
    
    try:
        # Import the tool
        from src.tools.scope_agkit_idea_tool import scope_agkit_idea_tool
        
        logger.info(f"🚀 Direct AgentKit idea scoping: {query[:100]}...")
        
        # Call the tool directly
        result = scope_agkit_idea_tool._run(
            query=query,
            mode=mode,
            complexity_level=complexity_level,
            project_id=project_id,
            include_agentkit=True
        )
        
        if "error" in result:
            logger.error(f"❌ Direct scoping failed: {result['error']}")
            return result
        
        logger.info(f"✅ Direct AgentKit idea scoped successfully")
        
        # Add summary for easy consumption
        result["direct_summary"] = {
            "agentkit_fit_score": result.get("agentkitAnalysis", {}).get("agentkitFitScore", 0),
            "web3_relevance": result.get("agentkitAnalysis", {}).get("web3Relevance", 0),
            "recommended_capabilities": result.get("agentkitAnalysis", {}).get("suggestedCapabilities", []),
            "integration_phases": len(result.get("agentkitAnalysis", {}).get("integrationRoadmap", [])),
            "complexity_level": complexity_level,
            "success": True
        }
        
        return result
        
    except Exception as e:
        error_msg = f"Direct AgentKit idea scoping failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {"error": error_msg, "success": False}

def register_scope_agkit_idea_agent(registry) -> str:
    """Register the Scope AgentKit Idea agent with the registry"""
    
    try:
        # Import the tool
        from src.tools.scope_agkit_idea_tool import scope_agkit_idea_tool
        
        # Create the workflow
        workflow = create_scope_agkit_idea_workflow(scope_agkit_idea_tool)
        
        # Register with the registry
        agent_id = registry.register_agent(workflow)
        
        logger.info(f"✅ Scope AgentKit Idea agent registered with ID: {agent_id}")
        
        return agent_id
        
    except Exception as e:
        logger.error(f"❌ Failed to register Scope AgentKit Idea agent: {e}")
        raise e

def test_scope_agkit_idea_agent(agent_id: str, registry) -> Dict[str, Any]:
    """Test the Scope AgentKit Idea agent with a sample idea"""
    
    try:
        # Test with a sample DeFi idea
        test_inputs = {
            "query": "A decentralized trading platform with automated portfolio rebalancing and yield optimization",
            "mode": "builder",
            "complexity_level": "advanced",
            "project_id": "test-defi-platform"
        }
        
        logger.info(f"🧪 Testing Scope AgentKit Idea agent with ID: {agent_id}")
        logger.info(f"📝 Test query: {test_inputs['query']}")
        
        # Execute the agent
        result = registry.handle({
            "type": "agent_call",
            "agent_id": agent_id,
            "inputs": test_inputs
        })
        
        logger.info(f"✅ Agent test completed successfully")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "test_inputs": test_inputs,
            "result": result,
            "message": "Scope AgentKit Idea agent test completed successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Agent test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "agent_id": agent_id
        }

# Export functions for easy import
__all__ = [
    'create_scope_agkit_idea_agent',
    'create_scope_agkit_idea_workflow', 
    'scope_agkit_idea_direct',
    'register_scope_agkit_idea_agent',
    'test_scope_agkit_idea_agent'
]