from typing import Dict, List, Optional, Any
import spacy
from ..common.types import Workflow, RemoteTool
import logging
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, VectorParams, Distance, PointStruct
import uuid
from ..core.risk_analyzer import RiskAnalyzer

logger = logging.getLogger(__name__)

class Registry:
    def __init__(self):
        self.tools = {}
        self.agents = {}  # Initialize agents dictionary
        self.nlp = spacy.load("en_core_web_md")
        self.client = QdrantClient(":memory:")
        self.risk_analyzer = RiskAnalyzer()
        
        # Create collections with correct vector dimensions
        if not self.client.collection_exists("tools"):
            self.client.create_collection(
                collection_name="tools",
                vectors_config=VectorParams(
                    size=300,  # spacy's en_core_web_md uses 300 dimensions
                    distance=Distance.COSINE
                )
            )
        
        if not self.client.collection_exists("agents"):
            self.client.create_collection(
                collection_name="agents",
                vectors_config=VectorParams(
                    size=300,
                    distance=Distance.COSINE
                )
            )
    
    def register_tool(self, name: str, tool: Any) -> None:
        self.tools[name] = tool
        # Store in Qdrant
        description = getattr(tool, 'description', str(tool))
        class_name = getattr(tool, 'class_name', tool.__class__.__name__)
        
        # Generate a UUID for the point ID
        tool_id = str(uuid.uuid4())
        
        try:
            # Convert vector to list and ensure all values are float
            vector = [float(x) for x in self.nlp(f"{name} {description}").vector.tolist()]
            
            # Create point using PointStruct
            point = PointStruct(
                id=tool_id,
                payload={
                    "name": name,
                    "description": description,
                    "class_name": class_name
                },
                vector=vector
            )
            
            self.client.upsert(
                collection_name="tools",
                points=[point]
            )
            logger.info(f"Registered tool: {name}")
        except Exception as e:
            logger.error(f"Failed to register tool in Qdrant: {str(e)}")
            # Continue even if Qdrant registration fails
            pass
    
    def register_agent(self, workflow: Workflow) -> str:
        """Register an agent workflow"""
        agent_id = str(uuid.uuid4())
        self.agents[agent_id] = workflow
        
        try:
            # Convert vector to list and ensure all values are float
            vector = [float(x) for x in self.nlp(f"{workflow.name} {workflow.description}").vector.tolist()]
            
            # Create point using PointStruct
            point = PointStruct(
                id=agent_id,
                payload={
                    "name": workflow.name,
                    "description": workflow.description,
                    "workflow": workflow.dict()
                },
                vector=vector
            )
            
            self.client.upsert(
                collection_name="agents",
                points=[point]
            )
            logger.info(f"Registered agent: {workflow.name}")
        except Exception as e:
            logger.error(f"Failed to register agent in Qdrant: {str(e)}")
            # Continue even if Qdrant registration fails
            pass
            
        return agent_id
    
    def find_tools(self, query: str) -> List[Dict[str, Any]]:
        """Find tools using semantic search"""
        if not query.strip():
            # Return all tools if query is empty
            return [
                {
                    "name": name,
                    "description": tool.description,
                    "similarity": 1.0
                }
                for name, tool in self.tools.items()
            ]
            
        query_vector = self.nlp(query.lower()).vector
        search_result = self.client.search(
            collection_name="tools",
            query_vector=query_vector,
            limit=10
        )
        
        return [
            {
                "name": hit.payload["name"],
                "description": hit.payload["description"],
                "similarity": hit.score
            }
            for hit in search_result
        ]
    
    def find_agents(self, query: str) -> List[Dict[str, Any]]:
        """Find agents using semantic search"""
        if not query.strip():
            # Return all agents if query is empty
            return [
                {
                    "id": agent_id,
                    "name": workflow.name,
                    "description": workflow.description,
                    "similarity": 1.0
                }
                for agent_id, workflow in self.agents.items()
            ]
        
        try:
            query_vector = [float(x) for x in self.nlp(query.lower()).vector.tolist()]
            search_result = self.client.search(
                collection_name="agents",
                query_vector=query_vector,
                limit=10
            )
            
            return [
                {
                    "id": hit.id,
                    "name": hit.payload["name"],
                    "description": hit.payload["description"],
                    "similarity": hit.score
                }
                for hit in search_result
            ]
        except Exception as e:
            logger.error(f"Failed to search agents in Qdrant: {str(e)}")
            # Return empty list on error
            return []
    
    async def execute_agent(self, agent_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an agent with the given context"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
            
        workflow = self.agents[agent_id]
        # Analyze risks before execution
        if "token_address" in context:
            risk_assessment = await self.risk_analyzer.analyze_trade_risk(
                token=context["token_address"],
                amount=context.get("amount", 0),
                price=context.get("price", 0),
                market_data=context.get("market_data", {})
            )
            
            # Add risk assessment to context
            context["risk_assessment"] = risk_assessment
            
            # Check for extreme risks
            if risk_assessment.overall_risk == "extreme":
                logger.warning(f"Extreme risk detected for agent {workflow.name}")
                
        # Execute workflow logic here
        results = {}
        for task_name, task in workflow.tasks.items():
            agent = workflow.agents[task.agent]
            
            # Get tools for agent
            agent_tools = {
                name: self.tools[name]
                for name in agent.agent_tools
                if name in self.tools
            }
            
            # Execute task
            task_result = await self._execute_task(
                task=task,
                tools=agent_tools,
                params=context
            )
            
            results[task_name] = task_result
            
        return {
            "status": "success",
            "workflow": workflow.name,
            "results": results,
            "risk_assessment": context.get("risk_assessment")
        }
    
    async def _execute_task(
        self,
        task: Any,
        tools: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single task with given tools and parameters"""
        try:
            # Format task description with parameters
            description = task.description.format(**params)
            
            # Execute each tool
            tool_results = {}
            for tool_name, tool in tools.items():
                result = await tool.execute(params)
                tool_results[tool_name] = result
                
            return {
                "description": description,
                "tool_results": tool_results,
                "expected_output": task.expected_output
            }
            
        except Exception as e:
            logger.error(f"Failed to execute task: {str(e)}", exc_info=True)
            raise
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents"""
        return [
            {
                "id": agent_id,
                "name": workflow.name,
                "description": workflow.description
            }
            for agent_id, workflow in self.agents.items()
        ]
