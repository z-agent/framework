from typing import Union, Dict, Optional, Any, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, APIRouter, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import time
from .registry import Registry
from .execution_monitor import execution_monitor
from .execution_storage import ExecutionStorage
from ..common.types import Workflow, Agent, Task, MultiModalRequest, MediaContent, MediaType
from ..tools.github_linear_integration import GitHubLinearIntegrationTool, GitHubConfig, LinearConfig as GitHubLinearConfig
import base64
import os
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ChatSessionStorage:
    """Qdrant-backed chat session storage (modular, non-breaking)."""

    def __init__(self, qdrant_client):
        self.qdrant_client = qdrant_client
        self.collection_name = "chat_sessions"
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        try:
            # Prefer collection_exists if available
            if hasattr(self.qdrant_client, "collection_exists"):
                exists = self.qdrant_client.collection_exists(self.collection_name)
                if not exists:
                    self.qdrant_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config={"size": 1536, "distance": "Cosine"},
                    )
                return
            # Fallback to get_collections
            collections = self.qdrant_client.get_collections()
            names = [c.name for c in collections.collections]
            if self.collection_name not in names:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={"size": 1536, "distance": "Cosine"},
                )
        except Exception as e:
            logger.warning(f"ChatSessionStorage collection setup warning: {e}")

    def create_session(self, agent_id: str, title: Optional[str] = None) -> str:
        session_id = str(uuid.uuid4())
        payload = {
            "session_id": session_id,
            "agent_id": agent_id,
            "title": title or "Chat Session",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
        }
        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=[{"id": session_id, "vector": [0.0] * 1536, "payload": payload}],
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            res = self.qdrant_client.retrieve(collection_name=self.collection_name, ids=[session_id])
            return res[0].payload if res else None
        except Exception:
            return None

    def append_message(self, session_id: str, role: str, content: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        session.setdefault("messages", []).append(message)
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[{"id": session_id, "vector": [0.0] * 1536, "payload": session}],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to append chat message: {e}")
            return False

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            points = result[0] if result and len(result) > 0 else []
            return [p.payload for p in points]
        except Exception as e:
            logger.error(f"Failed to list chat sessions: {e}")
            return []


class AgentCallRequest(BaseModel):
    query: Optional[str] = None
    task: Optional[str] = None
    context: Optional[Union[str, Dict[str, Any]]] = None
    media: Optional[list] = None  # For multi-modal content
    
    # Allow any additional fields
    class Config:
        extra = "allow"


class MultiModalAgentCallRequest(BaseModel):
    query: str
    media_files: Optional[list] = None
    context: Optional[Dict] = None


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


class ToolCallRequest(BaseModel):
    tool_id: str
    arguments: Dict[str, Any]


def create_api(registry: Registry):
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize execution storage
    execution_storage = ExecutionStorage(registry.qdrant_client)
    # Initialize chat session storage (modular and isolated)
    chat_storage = ChatSessionStorage(registry.qdrant_client)

    # Chat router (modular, pluggable)
    chat_router = APIRouter()

    class ChatSessionCreateRequest(BaseModel):
        agent_id: str
        title: Optional[str] = None

    class ChatMessageRequest(BaseModel):
        content: str
        context: Optional[Union[str, Dict[str, Any]]] = None

    @chat_router.post("/session")
    def create_chat_session(request: ChatSessionCreateRequest):
        try:
            # Validate agent exists
            records = registry.qdrant_client.retrieve(collection_name="agents", ids=[request.agent_id])
            if not records:
                raise HTTPException(status_code=404, detail="Agent not found")
            session_id = chat_storage.create_session(request.agent_id, request.title)
            return {"session_id": session_id}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @chat_router.get("/session/{session_id}")
    def get_chat_session(session_id: str):
        session = chat_storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @chat_router.get("/session/{session_id}/history")
    def get_chat_history(session_id: str):
        session = chat_storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"messages": session.get("messages", [])}

    def _build_agent_inputs(agent_id: str, message: str, context: Optional[Union[str, Dict[str, Any]]]):
        # Retrieve workflow to map input key safely
        record = registry.qdrant_client.retrieve(collection_name="agents", ids=[agent_id])[0]
        args: List[str] = record.payload.get("arguments", []) if record and record.payload else []
        inputs: Dict[str, Any] = {}
        if "query" in args:
            inputs["query"] = message
        elif "task" in args:
            inputs["task"] = message
        elif "input" in args:
            inputs["input"] = message
        # Only include context if declared
        if context is not None and "context" in args:
            inputs["context"] = context
        return inputs

    @chat_router.post("/session/{session_id}/message")
    def send_message(session_id: str, request: ChatMessageRequest):
        session = chat_storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        agent_id = session["agent_id"]
        # Append user message
        ok = chat_storage.append_message(session_id, "user", request.content)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to store user message")
        try:
            agent_inputs = _build_agent_inputs(agent_id, request.content, request.context)
            result = registry.execute_agent(agent_id, agent_inputs)
            result_text = str(result)
            # Append assistant message and persist execution
            chat_storage.append_message(session_id, "assistant", result_text)
            execution_storage.store_execution(agent_id, agent_inputs, result_text)
            return {"result": result_text}
        except Exception as e:
            logger.error(f"Chat message handling failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @chat_router.get("/session/{session_id}/stream")
    async def stream_chat(
        session_id: str,
        message: str,
        context: Optional[str] = None,
        stream_mode: str = "chunk",  # "chunk" (default) or "delta"
        chunk_size: int = 800,        # used when stream_mode = "chunk"
        delta_size: int = 40          # used when stream_mode = "delta"
    ):
        session = chat_storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        agent_id = session["agent_id"]

        async def event_stream():
            try:
                # Connected
                yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id, 'agent_id': agent_id, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                await asyncio.sleep(0.01)

                # Append user message
                chat_storage.append_message(session_id, "user", message)
                yield f"data: {json.dumps({'type': 'user_message', 'content': message, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

                # Build inputs and execute in background
                inputs = _build_agent_inputs(agent_id, message, context)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, registry.execute_agent, agent_id, inputs)
                result_text = str(result)

                # Streaming strategies (opt-in, non-breaking)
                if stream_mode == "delta":
                    total = max(1, len(result_text))
                    sent = 0
                    while sent < total:
                        nxt = min(total, sent + max(1, delta_size))
                        piece = result_text[sent:nxt]
                        yield f"data: {json.dumps({'type': 'assistant_delta', 'content': piece, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                        sent = nxt
                        await asyncio.sleep(0.02)
                    # Final assembled message for clients that expect one terminal message
                    yield f"data: {json.dumps({'type': 'assistant_message', 'content': result_text, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                else:
                    # Default chunk mode (backwards compatible)
                    if len(result_text) > chunk_size:
                        chunks = [result_text[i:i+chunk_size] for i in range(0, len(result_text), chunk_size)]
                        for idx, chunk in enumerate(chunks, 1):
                            yield f"data: {json.dumps({'type': 'assistant_chunk', 'chunk_number': idx, 'total_chunks': len(chunks), 'content': chunk, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                            await asyncio.sleep(0.05)
                    else:
                        yield f"data: {json.dumps({'type': 'assistant_message', 'content': result_text, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

                # Persist assistant message and execution
                chat_storage.append_message(session_id, "assistant", result_text)
                execution_storage.store_execution(agent_id, inputs, result_text)
                # No extra execution monitor context coupling

                # Done
                yield f"data: {json.dumps({'type': 'done', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "X-Accel-Buffering": "no",
            },
        )

    # Privy authentication router
    privy_router = APIRouter()

    class PrivySessionRequest(BaseModel):
        telegram_user_id: int
        privy_user_id: str
        access_token: str
        wallet_address: Optional[str] = None

    @privy_router.post("/session")
    async def save_privy_session(request: PrivySessionRequest):
        """Save Privy session data for wallet export functionality"""
        try:
            # Import Supabase service here to avoid circular imports
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

            # Initialize Supabase service
            try:
                from supabase_trading_service import get_trading_service
                supabase_service = get_trading_service()
            except Exception as e:
                logger.error(f"Failed to initialize Supabase: {e}")
                raise HTTPException(status_code=500, detail="Database not available")

            # Save session data to Supabase
            update_data = {
                'privy_user_id': request.privy_user_id,
                'session_signer': request.access_token,  # Store access token as session signer
            }

            if request.wallet_address:
                update_data['wallet_address'] = request.wallet_address

            success = await supabase_service.update_user(request.telegram_user_id, update_data)

            if success:
                logger.info(f"✅ Saved Privy session for user {request.telegram_user_id}")
                return {"success": True, "message": "Session saved successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to save session")

        except Exception as e:
            logger.error(f"Failed to save Privy session: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Mount routers
    app.include_router(privy_router, prefix="/privy", tags=["privy"])
    app.include_router(chat_router, prefix="/chat", tags=["chat"])

    @app.websocket("/agent_ws")
    async def agent_proxy(websocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_json()
            await websocket.send_json(registry.handle(data))

    @app.get("/tool_search")
    def tool_search(query: str):
        return registry.find_tools(query)

    @app.post("/save_agent")
    def save_agent(workflow_request: WorkflowRequest):
        try:
            # Convert the validated request to a Workflow object
            workflow = Workflow(
                name=workflow_request.name,
                description=workflow_request.description,
                arguments=workflow_request.arguments,
                agents={
                    name: Agent(**agent_config.model_dump())
                    for name, agent_config in workflow_request.agents.items()
                },
                tasks={
                    name: Task(**task_config.model_dump())
                    for name, task_config in workflow_request.tasks.items()
                },
            )
            agent_id = registry.register_agent(workflow)
            return {"agent_id": agent_id}
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/tool_call")
    def tool_call(request: ToolCallRequest):
        """Execute a tool directly with given arguments"""
        try:
            # Find the tool by ID or name
            tool_uuid = None
            
            # First try to find by UUID
            if request.tool_id in registry.tools:
                tool_uuid = request.tool_id
            else:
                # Try to find by name in tool_ids
                if request.tool_id in registry.tool_ids:
                    tool_uuid = registry.tool_ids[request.tool_id]
                else:
                    # Try to find by name in tools
                    for uuid, (tool_instance, remote_tool) in registry.tools.items():
                        if hasattr(remote_tool, 'class_name') and remote_tool.class_name == request.tool_id:
                            tool_uuid = uuid
                            break
            
            if not tool_uuid:
                raise HTTPException(status_code=404, detail=f"Tool {request.tool_id} not found")
            
            # Execute the tool using registry's execute_tool method
            result = registry.execute_tool(tool_uuid, request.arguments)
            
            return {
                "success": True,
                "tool_id": tool_uuid,
                "tool_name": request.tool_id,
                "arguments": request.arguments,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")

    @app.post("/agent_call")
    def agent_call(agent_id: str, request: AgentCallRequest, response: Response):
        try:
            # Build arguments dict based on what was provided
            arguments: Dict[str, Any] = {}
            
            # Get the raw request data to handle direct parameter passing
            request_dict = request.model_dump(exclude_none=True)
            
            # Handle direct parameter passing (like 'idea')
            if "idea" in request_dict:
                arguments["idea"] = request_dict["idea"]
            if "mode" in request_dict:
                arguments["mode"] = request_dict["mode"]
            if "complexity_level" in request_dict:
                arguments["complexity_level"] = request_dict["complexity_level"]
            if "project_id" in request_dict:
                arguments["project_id"] = request_dict["project_id"]
            
            # Handle standard fields
            if request.query is not None:
                arguments["query"] = request.query
            if request.task is not None:
                arguments["task"] = request.task
            if request.context is not None:
                arguments["context"] = request.context
            
            # Add any other additional fields from the request, ignore nulls/unknowns gracefully
            for key, value in request_dict.items():
                if key not in ["query", "task", "context", "media", "idea", "mode", "complexity_level", "project_id"]:
                    arguments[key] = value
            
            logger.info(f"Executing agent {agent_id} with arguments: {arguments}")
            result = registry.execute_agent(agent_id, arguments)
            logger.info(f"Agent execution completed successfully")
            
            # Convert CrewOutput to serializable format if needed
            if hasattr(result, 'raw'):
                # CrewOutput object - extract the raw result
                serializable_result = {
                    "result": result.raw,
                    "usage_metrics": getattr(result, 'usage_metrics', {}),
                    "tasks_output": [
                        {
                            "description": task.description if hasattr(task, 'description') else str(task),
                            "output": task.raw if hasattr(task, 'raw') else str(task)
                        } for task in getattr(result, 'tasks_output', [])
                    ]
                }
            else:
                serializable_result = result
            
            # Set proper response headers to close connection
            response.headers["Connection"] = "close"
            
            return serializable_result
            
        except Exception as e:
            logger.error(f"Agent call failed for agent_id {agent_id}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Return more detailed error information
            error_detail = f"Agent execution failed: {str(e)}"
            if hasattr(e, '__cause__') and e.__cause__:
                error_detail += f" (Caused by: {str(e.__cause__)})"
            
            raise HTTPException(status_code=500, detail=error_detail)

    @app.post("/direct_scope_agkit_idea")
    def direct_scope_agkit_idea(request: AgentCallRequest, response: Response):
        """Direct AgentKit idea scoping without agent overhead - most efficient approach"""
        try:
            # Import the direct function
            from src.agents.scope_agkit_idea_agent import scope_agkit_idea_direct
            
            # Extract parameters from request
            idea = request.arguments.get("idea") if request.arguments else None
            if not idea:
                # Try to get from other fields
                idea = request.query or request.task or request.context
                
            if not idea:
                raise HTTPException(status_code=400, detail="No idea provided. Please provide 'idea' in the request body.")
            
            mode = request.arguments.get("mode", "builder") if request.arguments else "builder"
            complexity_level = request.arguments.get("complexity_level", "medium") if request.arguments else "medium"
            project_id = request.arguments.get("project_id") if request.arguments else None
            
            logger.info(f"🚀 Direct AgentKit idea scoping: {idea[:100]}...")
            
            # Call the direct function (no agent, no LLM calls)
            result = scope_agkit_idea_direct(
                idea=idea,
                mode=mode,
                complexity_level=complexity_level,
                project_id=project_id
            )
            
            if "error" in result:
                logger.error(f"❌ Direct scoping failed: {result['error']}")
                raise HTTPException(status_code=500, detail=result['error'])
            
            logger.info(f"✅ Direct AgentKit idea scoped successfully")
            
            # Set proper response headers
            response.headers["Connection"] = "close"
            
            return {
                "success": True,
                "message": "Direct AgentKit idea scoping completed successfully",
                "result": result,
                "efficiency": "No unnecessary LLM calls - direct tool execution"
            }
            
        except Exception as e:
            logger.error(f"Direct AgentKit idea scoping failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Direct scoping failed: {str(e)}")

    @app.post("/multimodal_agent_call")
    async def multimodal_agent_call(agent_id: str, request: MultiModalAgentCallRequest):
        """Execute agent with multi-modal content"""
        try:
            # Process media files
            processed_media = []
            if request.media_files:
                for media_file in request.media_files:
                    media_content = MediaContent(
                        type=MediaType(media_file.get("type", "text")),
                        content=media_file.get("content"),
                        mime_type=media_file.get("mime_type")
                    )
                    processed_media.append(media_content)
            
            # Create multi-modal request
            multimodal_request = MultiModalRequest(
                query=request.query,
                media=processed_media,
                context=request.context
            )
            
            return registry.execute_multimodal_agent(agent_id, multimodal_request)
        except Exception as e:
            logger.error(f"Multi-modal agent execution error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upload_media")
    async def upload_media(file: UploadFile = File(...)):
        """Upload media file and return base64 encoded content"""
        try:
            content = await file.read()
            encoded_content = base64.b64encode(content).decode('utf-8')
            
            return {
                "filename": file.filename,
                "content": encoded_content,
                "mime_type": file.content_type,
                "size_bytes": len(content)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/supported_media_types")
    def get_supported_media_types():
        """Get list of supported media types"""
        return {
            "supported_types": [
                {"type": "text", "extensions": [".txt", ".md"]},
                {"type": "image", "extensions": [".jpg", ".jpeg", ".png", ".gif", ".webp"]},
                {"type": "audio", "extensions": [".mp3", ".wav", ".m4a", ".ogg"]},
                {"type": "video", "extensions": [".mp4", ".avi", ".mov", ".webm"]},
                {"type": "document", "extensions": [".pdf", ".doc", ".docx"]}
            ]
        }

    @app.get("/agent_search")
    def agent_search(query: str = ""):
        """Search agents by query string"""
        if not query:
            raise HTTPException(status_code=422, detail="Query parameter is required")
        return registry.find_agents(query)

    @app.get("/agent_list")
    def agent_list():
        """Get a clean list of all available agents"""
        try:
            agents_data = registry.list_agents()
            
            # Handle Qdrant scroll response format
            if agents_data and len(agents_data) > 0:
                # Qdrant scroll returns [points, next_page_offset]
                agents = agents_data[0] if isinstance(agents_data[0], list) else agents_data
                
                # Clean and structure each agent
                cleaned_agents = []
                for agent in agents:
                    if not agent:
                        continue
                    # Support both dict-like and object-like points
                    if hasattr(agent, 'payload') and agent.payload is not None:
                        cleaned_agent = {
                            "id": getattr(agent, 'id', None),
                            "name": agent.payload.get("name", "Unknown"),
                            "description": agent.payload.get("description", ""),
                        }
                        cleaned_agents.append(cleaned_agent)
                    elif isinstance(agent, dict) and 'payload' in agent:
                        cleaned_agent = {
                            "id": agent.get("id"),
                            "name": (agent.get("payload") or {}).get("name", "Unknown"),
                            "description": (agent.get("payload") or {}).get("description", ""),
                        }
                        cleaned_agents.append(cleaned_agent)
                
                return {
                    "agents": cleaned_agents,
                    "count": len(cleaned_agents)
                }
            else:
                return {"agents": [], "count": 0}
                
        except Exception as e:
            logger.error(f"Error fetching agents: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch agents: {str(e)}")

    @app.get("/tool_list")
    def tool_list():
        """Get a clean list of all available tools"""
        try:
            # Get tools from Qdrant
            tools_data = registry.list_tools()
            
            # Handle Qdrant scroll response format
            if tools_data and len(tools_data) > 0:
                # Qdrant scroll returns [points, next_page_offset]
                tools = tools_data[0] if isinstance(tools_data[0], list) else tools_data
                
                # Clean and structure each tool
                cleaned_tools = []
                for tool in tools:
                    if not tool:
                        continue
                    if hasattr(tool, 'payload') and tool.payload is not None:
                        cleaned_tool = {
                            "id": getattr(tool, 'id', None),
                            "name": tool.payload.get("id", "Unknown"),
                            "description": tool.payload.get("description", ""),
                            "class_name": tool.payload.get("class_name", "")
                        }
                        cleaned_tools.append(cleaned_tool)
                    elif isinstance(tool, dict) and 'payload' in tool:
                        payload = tool.get("payload") or {}
                        cleaned_tool = {
                            "id": tool.get("id"),
                            "name": payload.get("id", "Unknown"),
                            "description": payload.get("description", ""),
                            "class_name": payload.get("class_name", "")
                        }
                        cleaned_tools.append(cleaned_tool)
                
                return {
                    "tools": cleaned_tools,
                    "count": len(cleaned_tools)
                }
            else:
                return {"tools": [], "count": 0}
                
        except Exception as e:
            logger.error(f"Error fetching tools: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch tools: {str(e)}")
    
    @app.post("/force_register_tools")
    def force_register_tools():
        """Force re-registration of all tools"""
        try:
            # This will trigger the registry to re-register tools
            # Since the server is running the old code, we need to restart
            return {
                "message": "Tools need to be re-registered. Please restart the server to pick up registry.py changes.",
                "status": "restart_required"
            }
        except Exception as e:
            return {"error": str(e)}

    @app.get("/health")
    def health_check():
        """Health check endpoint for Docker and load balancers"""
        return {
            "status": "healthy",
            "timestamp": "2025-01-13T10:00:00Z",
            "service": "Zara Framework API",
            "version": "1.0.0"
        }
    


    @app.get("/stream/{agent_id}")
    async def stream_agent_execution(agent_id: str, query: str = ""):
        """Stream real-time agent execution using Server-Sent Events"""
        logger.info(f"🚀 Starting SSE stream for agent_id: {agent_id}, query: {query}")
        
        async def event_stream():
            try:
                import asyncio
                import time
                
                # Send initial connection event IMMEDIATELY
                timestamp = datetime.now(timezone.utc).isoformat()
                connection_event = {'type': 'connected', 'agent_id': agent_id, 'query': query, 'timestamp': timestamp}
                logger.info(f"📡 Sending connection event: {connection_event}")
                yield f"data: {json.dumps(connection_event)}\n\n"
                
                # Flush immediately
                await asyncio.sleep(0.01)
                
                # Send agent start event IMMEDIATELY  
                agent_start_event = {'type': 'agent_start', 'message': f'🤖 Starting agent {agent_id}', 'timestamp': datetime.now(timezone.utc).isoformat()}
                logger.info(f"📡 Sending agent start event: {agent_start_event}")
                yield f"data: {json.dumps(agent_start_event)}\n\n"
                
                # Send workflow loading event
                workflow_event = {'type': 'workflow_loaded', 'message': '📋 Loading agent workflow...', 'timestamp': datetime.now(timezone.utc).isoformat()}
                logger.info(f"📡 Sending workflow event: {workflow_event}")
                yield f"data: {json.dumps(workflow_event)}\n\n"
                
                # Send thinking event
                yield f"data: {json.dumps({'type': 'thinking', 'message': '🧠 Analyzing query and planning tasks...', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                
                # Send crew setup event
                yield f"data: {json.dumps({'type': 'crew_setup', 'message': '👥 Setting up agent crew and tasks...', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                
                # Try to execute real agent if available
                try:
                    logger.info(f"🔍 Attempting to retrieve agent workflow for ID: {agent_id}")
                    workflow = registry.qdrant_client.retrieve(
                        collection_name="agents", ids=[agent_id]
                    )[0]
                    
                    if workflow:
                        execution_event = {'type': 'execution_log', 'message': '🚀 Executing real agent workflow...', 'timestamp': datetime.now(timezone.utc).isoformat()}
                        logger.info(f"📡 Sending execution event: {execution_event}")
                        yield f"data: {json.dumps(execution_event)}\n\n"
                        
                        # Execute agent in thread to avoid blocking
                        logger.info(f"⚡ Starting real agent execution for query: {query}")
                        loop = asyncio.get_event_loop()
                        
                        # Start execution monitoring
                        execution_id = f"stream_{agent_id}_{str(uuid.uuid4())}"
                        execution_monitor.start_execution(execution_id, agent_id)
                        
                        # Stream initial progress
                        yield f"data: {json.dumps({'type': 'execution_progress', 'message': '📊 Agent execution in progress...', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                        
                        # Execute agent asynchronously
                        result = await loop.run_in_executor(None, registry.execute_agent, agent_id, {"query": query})
                        
                        # Stream execution progress in real-time
                        yield f"data: {json.dumps({'type': 'execution_progress', 'message': '📊 Agent execution in progress...', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                        
                        # Get execution monitoring data
                        execution_status = None
                        for exec_id, exec_data in execution_monitor.active_executions.items():
                            if exec_data['agent_id'] == agent_id and exec_data['status'] == 'completed':
                                execution_status = exec_data
                                break
                        
                        if execution_status:
                            # Stream detailed execution data
                            yield f"data: {json.dumps({'type': 'execution_details', 'message': '🔍 Execution details available', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                            
                            # Stream progress updates if available
                            if execution_status.get('progress_updates'):
                                progress_count = len(execution_status["progress_updates"])
                                yield f"data: {json.dumps({'type': 'progress_updates_start', 'message': f'📊 {progress_count} progress updates available', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                                
                                for progress_update in execution_status['progress_updates']:
                                    progress_event = {
                                        'type': 'progress_update',
                                        'step': progress_update.get('step', 'Unknown'),
                                        'message': progress_update.get('message', ''),
                                        'details': progress_update.get('details', ''),
                                        'step_number': progress_update.get('step_number', 0),
                                        'timestamp': progress_update.get('timestamp', datetime.now(timezone.utc).isoformat())
                                    }
                                    yield f"data: {json.dumps(progress_event)}\n\n"
                                    await asyncio.sleep(0.1)
                            
                            # Stream tool calls if available
                            if execution_status.get('tool_calls'):
                                tool_count = len(execution_status["tool_calls"])
                                yield f"data: {json.dumps({'type': 'tool_execution_start', 'message': f'🔧 {tool_count} tools executed', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                                
                                for i, tool_call in enumerate(execution_status['tool_calls'], 1):
                                    tool_event = {
                                        'type': 'tool_execution',
                                        'tool_name': tool_call.get('tool_name', 'Unknown Tool'),
                                        'input': tool_call.get('input', ''),
                                        'output': tool_call.get('output', '')[:500] + '...' if len(str(tool_call.get('output', ''))) > 500 else str(tool_call.get('output', '')),
                                        'execution_order': i,
                                        'step_number': tool_call.get('step_number', 0),
                                        'timestamp': tool_call.get('timestamp', datetime.now(timezone.utc).isoformat())
                                    }
                                    yield f"data: {json.dumps(tool_event)}\n\n"
                                    await asyncio.sleep(0.2)  # Faster streaming
                            
                            # Stream execution metadata
                            if execution_status.get('start_time') and execution_status.get('end_time'):
                                duration = execution_status['end_time'] - execution_status['start_time']
                                metadata_event = {
                                    'type': 'execution_metadata',
                                    'duration_seconds': duration,
                                    'status': execution_status.get('status', 'unknown'),
                                    'current_step': execution_status.get('current_step', 'unknown'),
                                    'total_steps': execution_status.get('step_count', 0),
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                }
                                yield f"data: {json.dumps(metadata_event)}\n\n"
                        
                        # Stream the final result
                        logger.info(f"✅ Agent execution completed. Result length: {len(str(result))} chars")
                        
                        # Split result into chunks for better streaming
                        result_str = str(result)
                        if len(result_str) > 1000:
                            # Stream result in chunks
                            chunks = [result_str[i:i+1000] for i in range(0, len(result_str), 1000)]
                            for i, chunk in enumerate(chunks):
                                chunk_event = {
                                    'type': 'result_chunk',
                                    'chunk_number': i + 1,
                                    'total_chunks': len(chunks),
                                    'content': chunk,
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                }
                                yield f"data: {json.dumps(chunk_event)}\n\n"
                                await asyncio.sleep(0.1)
                            
                            # Final result summary
                            result_event = {
                                'type': 'execution_result', 
                                'message': f'📊 Agent execution completed - {len(chunks)} chunks delivered', 
                                'result_summary': result_str[:200] + '...',
                                'total_length': len(result_str),
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                        else:
                            result_event = {
                                'type': 'execution_result', 
                                'message': '📊 Agent execution completed', 
                                'result': result_str, 
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                        
                        logger.info(f"📡 Sending result event: {result_event}")
                        yield f"data: {json.dumps(result_event)}\n\n"
                        
                    else:
                        logger.error(f"❌ No workflow found for agent_id: {agent_id}")
                        error_event = {'type': 'error', 'message': f'❌ No agent workflow found for ID: {agent_id}', 'timestamp': datetime.now(timezone.utc).isoformat()}
                        yield f"data: {json.dumps(error_event)}\n\n"
                        
                except Exception as agent_error:
                    logger.error(f"❌ Agent execution error: {str(agent_error)}")
                    error_event = {'type': 'error', 'message': f'❌ Agent execution failed: {str(agent_error)[:200]}...', 'timestamp': datetime.now(timezone.utc).isoformat()}
                    yield f"data: {json.dumps(error_event)}\n\n"
                
                # Final completion event
                yield f"data: {json.dumps({'type': 'done', 'message': '✅ Stream completed successfully', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                
            except Exception as e:
                error_event = {"type": "error", "message": f"Streaming error: {str(e)}", "timestamp": datetime.now(timezone.utc).isoformat()}
                yield f"data: {json.dumps(error_event)}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    # GitHub webhook endpoint
    @app.post("/github/webhook")
    async def github_webhook(request: Request):
        """Handle GitHub webhooks for PR events"""
        try:
            # Get the raw body for signature verification
            body = await request.body()
            signature = request.headers.get("X-Hub-Signature-256", "")
            
            # Verify webhook signature
            github_config = GitHubConfig(
                webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", "default_secret"),
                api_token=os.getenv("GITHUB_API_TOKEN", "")
            )
            
            linear_config = GitHubLinearConfig(
                api_key=os.getenv("LINEAR_API_KEY", ""),
                team_id=os.getenv("LINEAR_TEAM_ID", "")
            )
            
            # Verify signature
            integration_tool = GitHubLinearIntegrationTool(github_config, linear_config)
            if not integration_tool.verify_webhook_signature(body, signature):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
            
            # Parse the webhook payload
            payload = json.loads(body.decode('utf-8'))
            event_type = request.headers.get("X-GitHub-Event", "")
            
            # Only process PR events
            if event_type != "pull_request":
                return {"message": f"Ignored event type: {event_type}"}
            
            action = payload.get("action", "")
            if action not in ["opened", "synchronize", "reopened"]:
                return {"message": f"Ignored PR action: {action}"}
            
            # Extract PR information
            pr_data = payload.get("pull_request", {})
            pr_url = pr_data.get("html_url", "")
            
            if not pr_url:
                raise HTTPException(status_code=400, detail="No PR URL found in webhook")
            
            # Create GitHub-Linear integration tool
            integration_tool = GitHubLinearIntegrationTool(github_config, linear_config)
            
            # Process PR and create Linear issues
            result = integration_tool._run(pr_url, "review")
            
            if result["success"]:
                logger.info(f"Successfully processed PR {pr_url}: {result['issues_created']} issues created")
                return {
                    "success": True,
                    "message": f"PR processed successfully. {result['issues_created']} Linear issues created.",
                    "pr_url": pr_url,
                    "issues_created": result["issues_created"],
                    "review_issues": result["review_issues"]
                }
            else:
                logger.error(f"Failed to process PR {pr_url}: {result.get('error', 'Unknown error')}")
                raise HTTPException(status_code=500, detail=f"Failed to process PR: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"GitHub webhook error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

    # Manual PR processing endpoint
    @app.post("/github/process-pr")
    async def process_pr_manually(pr_url: str):
        """Manually process a GitHub PR and create Linear issues"""
        try:
            github_config = GitHubConfig(
                webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", "default_secret"),
                api_token=os.getenv("GITHUB_API_TOKEN", "")
            )
            
            linear_config = GitHubLinearConfig(
                api_key=os.getenv("LINEAR_API_KEY", ""),
                team_id=os.getenv("LINEAR_TEAM_ID", "")
            )
            
            # Create GitHub-Linear integration tool
            integration_tool = GitHubLinearIntegrationTool(github_config, linear_config)
            
            # Process PR and create Linear issues
            result = integration_tool._run(pr_url, "review")
            
            if result["success"]:
                return {
                    "success": True,
                    "message": f"PR processed successfully. {result['issues_created']} Linear issues created.",
                    "pr_url": pr_url,
                    "issues_created": result["issues_created"],
                    "review_issues": result["review_issues"]
                }
            else:
                raise HTTPException(status_code=500, detail=f"Failed to process PR: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Manual PR processing error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"PR processing failed: {str(e)}")

    # Linear webhook endpoint for receiving events
    @app.post("/linear/webhook")
    async def linear_webhook(request: Request):
        """Handle Linear webhook events for agent sessions"""
        try:
            # Get webhook data
            webhook_data = await request.json()
            
            # Initialize Linear configuration
            from ..tools.linear_tools import LinearConfig, LinearWebhookHandler
            from ..tools.github_linear_integration import GitHubLinearIntegrationTool, GitHubConfig, LinearConfig as GitHubLinearConfig
            
            linear_config = LinearConfig(
                api_key=os.getenv("LINEAR_API_KEY", ""),
                webhook_secret=os.getenv("LINEAR_WEBHOOK_SECRET", ""),
                base_url="https://api.linear.app/graphql"
            )
            
            # Create webhook handler
            webhook_handler = LinearWebhookHandler(linear_config)
            
            # Handle the webhook
            result = webhook_handler.handle_webhook(webhook_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Linear webhook error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    # Execution storage endpoints
    @app.get("/executions")
    def list_executions(limit: int = 50, offset: int = 0):
        """List recent executions"""
        try:
            executions = execution_storage.list_executions(limit=limit, offset=offset)
            return {
                "executions": executions,
                "count": len(executions),
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/executions/{execution_id}")
    def get_execution(execution_id: str):
        """Get execution by ID"""
        try:
            execution = execution_storage.get_execution(execution_id)
            if not execution:
                raise HTTPException(status_code=404, detail="Execution not found")
            return execution
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/executions/{execution_id}/rate")
    def rate_execution(execution_id: str, rating: int, feedback: str = ""):
        """Rate an execution result"""
        try:
            if not 1 <= rating <= 5:
                raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
            
            success = execution_storage.rate_execution(execution_id, rating, feedback)
            if not success:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            return {"success": True, "message": "Rating saved"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/search/executions")
    def search_executions(query: str, limit: int = 20):
        """Search executions by query"""
        try:
            executions = execution_storage.search_executions(query, limit=limit)
            return {
                "executions": executions,
                "count": len(executions),
                "query": query,
                "limit": limit
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/browse/ideas")
    def browse_ideas(category: str = None, rating_min: float = 0.0, limit: int = 20):
        """Browse generated startup ideas"""
        try:
            executions = execution_storage.list_executions(limit=1000)
            
            # Filter by category and rating
            filtered = []
            for execution in executions:
                if category and category not in execution.get("tags", []):
                    continue
                if execution.get("rating", 0) < rating_min:
                    continue
                filtered.append(execution)
            
            # Sort by rating (highest first)
            filtered.sort(key=lambda x: x.get("rating", 0) or 0, reverse=True)
            
            return {
                "ideas": filtered[:limit],
                "count": len(filtered),
                "category": category,
                "rating_min": rating_min
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/summarize/executions")
    def summarize_executions(limit: int = 20):
        """Get AI-powered summary of recent executions"""
        try:
            # Get recent executions
            executions = execution_storage.list_executions(limit=limit)
            
            if not executions:
                return {"message": "No executions found to summarize"}
            
            # Create summary using the summarizer agent
            summary = registry.create_summarizer_agent(executions)
            
            return {
                "summary": summary,
                "executions_analyzed": len(executions),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/create_workflow")
    def create_workflow(use_case: str, query: str):
        """Create a dynamic workflow based on use case and query"""
        try:
            workflow = registry.create_dynamic_workflow(use_case, query)
            
            # Store the workflow in Qdrant
            workflow_id = str(uuid.uuid4())
            registry.qdrant_client.upsert(
                collection_name="agents",
                points=[{
                    "id": workflow_id,
                    "vector": [0.1] * 1536,  # Placeholder vector
                    "payload": {
                        "name": workflow.name,
                        "description": workflow.description,
                        "agents": {name: {
                            "name": agent.name,
                            "role": agent.role,
                            "goal": agent.goal,
                            "backstory": agent.backstory,
                            "tools": agent.tools,
                            "agent_tools": agent.agent_tools
                        } for name, agent in workflow.agents.items()},
                        "tasks": {name: {
                            "name": task.name,
                            "description": task.description,
                            "agent": task.agent,
                            "expected_output": task.expected_output,
                            "context": task.context,
                            "arguments": task.arguments
                        } for name, task in workflow.tasks.items()},
                        "arguments": workflow.arguments
                    }
                }]
            )
            
            return {
                "workflow_id": workflow_id,
                "workflow": {
                    "name": workflow.name,
                    "description": workflow.description,
                    "agents": list(workflow.agents.keys()),
                    "tasks": list(workflow.tasks.keys())
                },
                "message": f"Created {use_case} workflow for: {query}"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


def extract_tool_arguments(description: str) -> dict:
    """Extract tool arguments from description string"""
    try:
        if "Tool Arguments:" in description:
            args_section = description.split("Tool Arguments:")[1].split("Tool Description:")[0].strip()
            # Parse the arguments string into a proper dict
            # This is a simple parser - you might want to enhance it
            args = {}
            if args_section and args_section != "{}":
                # Remove the outer braces and parse
                args_str = args_section.strip("{}")
                if args_str:
                    # Simple parsing - split by comma and parse each key-value
                    pairs = args_str.split(",")
                    for pair in pairs:
                        if ":" in pair:
                            key, value = pair.split(":", 1)
                            key = key.strip().strip("'\"")
                            value = value.strip().strip("'\"")
                            args[key] = value
            return args
        return {}
    except Exception:
        return {}
