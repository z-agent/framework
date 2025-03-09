"""
API Server for DeFi NLP Service
Implements FastAPI endpoints with monitoring
"""

from typing import Union, Dict, Optional, Any
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .registry import Registry
from ..common.types import Workflow, Agent, Task
from ..core.nlp_service import NLPService, NLPRequest, NLPResponse
import logging
from datetime import datetime, timedelta
import json
import asyncio
from redis import Redis
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import time
from prometheus_fastapi_instrumentator import Instrumentator
from typing import AsyncGenerator
from src.services.research_service import ResearchService, ResearchRequest

# Configure logging
logger = logging.getLogger(__name__)

# Configure tracing
tracer = trace.get_tracer(__name__)

class AgentCallRequest(BaseModel):
    query: str
    context: Optional[Dict[str, str]] = None

class AgentConfig(BaseModel):
    role: str
    goal: str
    backstory: str
    agent_tools: list[str]

class TaskConfig(BaseModel):
    description: str
    expected_output: str
    agent: str
    context: list[str] = []

class WorkflowRequest(BaseModel):
    name: str
    description: str
    arguments: list[str]
    agents: Dict[str, AgentConfig]
    tasks: Dict[str, TaskConfig]

class APIMetrics:
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.processing_times = []
        
    def record_request(self, processing_time: float, is_error: bool = False):
        self.request_count += 1
        if is_error:
            self.error_count += 1
        self.processing_times.append(processing_time)
        
        # Keep only last 1000 processing times
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]
    
    def get_metrics(self) -> Dict[str, Union[int, float]]:
        if not self.processing_times:
            return {
                "request_count": self.request_count,
                "error_count": self.error_count,
                "avg_processing_time": 0,
                "error_rate": 0
            }
        
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_processing_time": sum(self.processing_times) / len(self.processing_times),
            "error_rate": self.error_count / self.request_count if self.request_count > 0 else 0
        }

def create_api(
    registry: Registry,
    redis_url: Optional[str] = None,
    model_path: Optional[str] = None
):
    app = FastAPI(
        title="DeFi NLP API", 
        version="1.0.0",
        debug=True
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Initialize metrics
    metrics = APIMetrics()
    
    # Initialize NLP service
    nlp_service = NLPService(
        cache_url=redis_url,
        model_path=model_path
    )
    
    # Add Prometheus metrics
    Instrumentator().instrument(app).expose(app)
    
    # Add OpenTelemetry instrumentation
    FastAPIInstrumentor.instrument_app(app)

    research_service = ResearchService()

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    @app.websocket("/agent_ws")
    async def agent_proxy(websocket):
        await websocket.accept()
        while True:
            try:
                data = await websocket.receive_json()
                response = await registry.handle(data)
                await websocket.send_json(response)
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}", exc_info=True)
                await websocket.close(code=1011, reason=str(e))
                break

    @app.get("/tool_search")
    async def tool_search(query: str):
        start_time = time.time()
        try:
            result = registry.find_tools(query)
            metrics.record_request(time.time() - start_time)
            return result
        except Exception as e:
            metrics.record_request(time.time() - start_time, is_error=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/save_agent")
    async def save_agent(workflow_request: WorkflowRequest):
        start_time = time.time()
        try:
            workflow = Workflow(
                name=workflow_request.name,
                description=workflow_request.description,
                arguments=workflow_request.arguments,
                agents={
                    name: Agent(**agent_config.dict())
                    for name, agent_config in workflow_request.agents.items()
                },
                tasks={
                    name: Task(**task_config.dict())
                    for name, task_config in workflow_request.tasks.items()
                }
            )
            agent_id = registry.register_agent(workflow)
            metrics.record_request(time.time() - start_time)
            return {"agent_id": agent_id}
        except Exception as e:
            metrics.record_request(time.time() - start_time, is_error=True)
            logger.error(f"Error saving agent: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent_search")
    async def agent_search(query: str):
        start_time = time.time()
        try:
            result = registry.find_agents(query)
            metrics.record_request(time.time() - start_time)
            return result
        except Exception as e:
            metrics.record_request(time.time() - start_time, is_error=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/agent_call")
    async def agent_call(agent_id: str, request: AgentCallRequest):
        start_time = time.time()
        try:
            result = registry.execute_agent(
                agent_id,
                {
                    "query": request.query,
                    **(request.context or {})
                }
            )
            metrics.record_request(time.time() - start_time)
            return result
        except Exception as e:
            metrics.record_request(time.time() - start_time, is_error=True)
            logger.error(f"Error executing agent: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent_list")
    async def agent_list():
        start_time = time.time()
        try:
            result = registry.list_agents()
            metrics.record_request(time.time() - start_time)
            return result
        except Exception as e:
            metrics.record_request(time.time() - start_time, is_error=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/nlp/process", response_model=None)
    async def process_natural_language(
        request: NLPRequest,
        stream: bool = False
    ) -> NLPResponse:
        """Process natural language request with streaming support"""
        start_time = time.time()
        
        with tracer.start_as_current_span("nlp_process") as span:
            try:
                if stream:
                    return StreamingResponse(
                        stream_nlp_response(request),
                        media_type="application/json"
                    )
                
                response = await nlp_service.process_request(request)
                
                # If it's a trade intent with valid parameters, execute it
                if (response.intent.type == "trade" and 
                    response.action_params and 
                    "error" not in response.action_params):
                    
                    # Create a trading agent if needed
                    workflow = Workflow(
                        name="Trading Agent",
                        description="Agent for executing trades",
                        arguments=["query"],
                        agents={
                            "trader": Agent(
                                role="Trading Expert",
                                goal="Execute trades safely and efficiently",
                                backstory="Expert in DeFi trading",
                                agent_tools=["Solana Trade", "Solana Fetch Price"]
                            )
                        },
                        tasks={
                            "trade": Task(
                                description="{query}",
                                expected_output="Trade execution result",
                                agent="trader"
                            )
                        }
                    )
                    
                    agent_id = registry.register_agent(workflow)
                    
                    # Execute the trade
                    trade_result = registry.execute_agent(
                        agent_id,
                        {"query": request.text}
                    )
                    
                    # Add trade result to response
                    response.action_params["execution"] = trade_result
                
                metrics.record_request(time.time() - start_time)
                return response
                
            except Exception as e:
                metrics.record_request(time.time() - start_time, is_error=True)
                logger.error(
                    f"Error processing NLP request: {str(e)}",
                    exc_info=True
                )
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process request: {str(e)}"
                )

    async def stream_nlp_response(request: NLPRequest) -> AsyncGenerator[str, None]:
        """Stream NLP response for better UX"""
        try:
            response = await nlp_service.process_request(request)
            
            # Stream each part of the response
            yield json.dumps({"type": "intent", "data": response.intent.dict()}) + "\n"
            yield json.dumps({"type": "explanation", "data": response.explanation}) + "\n"
            
            if response.action_params:
                yield json.dumps({
                    "type": "parameters",
                    "data": response.action_params
                }) + "\n"
            
            if response.suggestions:
                yield json.dumps({
                    "type": "suggestions",
                    "data": response.suggestions
                }) + "\n"
            
            if response.risk_assessment:
                yield json.dumps({
                    "type": "risk",
                    "data": response.risk_assessment
                }) + "\n"
                
        except Exception as e:
            logger.error(f"Error streaming response: {str(e)}", exc_info=True)
            yield json.dumps({
                "type": "error",
                "data": {"message": str(e)}
            }) + "\n"

    @app.get("/metrics")
    async def get_metrics():
        """Get API metrics"""
        return metrics.get_metrics()

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }

    @app.post("/research/social")
    async def get_social_research(
        request: ResearchRequest,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Get social media research summary"""
        return await research_service.get_social_summary(request)
    
    @app.post("/research/coin")
    async def get_coin_research(
        request: ResearchRequest,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Get comprehensive coin research"""
        return await research_service.research_coin(request)
    
    @app.post("/research/schedule")
    async def schedule_research(
        request: ResearchRequest,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Schedule research tasks"""
        return await research_service.schedule_research(request, background_tasks)
    
    @app.get("/research/cache/clear")
    async def clear_research_cache() -> Dict[str, Any]:
        """Clear research cache"""
        await research_service.clear_cache()
        return {"message": "Research cache cleared", "timestamp": datetime.now()}

    return app
