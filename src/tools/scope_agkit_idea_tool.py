#!/usr/bin/env python3
"""
🚀 SCOPE AGENTKIT IDEA TOOL
Enhanced business idea scoping with AgentKit integration analysis
Integrates with the Zara Framework registry system
"""

import requests
import json
from typing import Dict, Any, List, Optional
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
import logging
import os
import dotenv
dotenv.load_dotenv()

logger = logging.getLogger(__name__)

class ScopeAgentKitIdeaSchema(BaseModel):
    """Schema for AgentKit-enhanced idea scoping"""
    query: str = Field(..., description="The business idea to scope and analyze for AgentKit integration")
    mode: str = Field(default="builder", description="Analysis mode: builder, investor, or founder")
    project_id: Optional[str] = Field(None, description="Optional project ID for tracking")
    include_agentkit: bool = Field(default=True, description="Include AgentKit integration analysis")
    complexity_level: str = Field(default="medium", description="AgentKit integration complexity: simple, medium, advanced")

class ScopeAgentKitIdeaTool(BaseTool):
    """Enhanced scope idea tool with AgentKit integration analysis"""
    name: str = "Scope AgentKit Idea Tool"
    description: str = "Analyzes business ideas for AgentKit integration potential, providing comprehensive Web3 and AI agent recommendations with implementation roadmaps and code examples"
    args_schema: type = ScopeAgentKitIdeaSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set instance variables after super().__init__()
        object.__setattr__(self, 'api_url', "https://enlsvqrfgktlndrnbojk.supabase.co/functions/v1/scope-agkit-idea")
        
        # Load API key with better debugging
        api_key = os.getenv('SUPABASE_ANON_KEY', '')
        print(f"🔑 API Key loaded: {'***' + api_key[-10:] if api_key else 'NOT FOUND'}")
        if not api_key:
            print("❌ SUPABASE_ANON_KEY not found in environment variables")
            print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k]}")
        
        object.__setattr__(self, 'api_key', api_key)
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        # Handle query parameter (keeping the original field name)
        query_raw = kwargs.get("query", "")
        print(f"TOOL RECEIVED kwargs: {kwargs}")
        print(f"TOOL query_raw: {query_raw}")
        
        if isinstance(query_raw, dict):
            # Extract from dictionary format
            query = query_raw.get("description", "").strip()
        else:
            # Handle string format
            query = str(query_raw).strip()
        print(f"TOOL FINAL query: {query}")
        
        mode = kwargs.get("mode", "builder").strip()
        project_id = kwargs.get("project_id")
        include_agentkit = kwargs.get("include_agentkit", True)
        complexity_level = kwargs.get("complexity_level", "medium").strip()
        
        if not query:
            return {"error": "No query provided for scoping"}
        
        if not self.api_key:
            return {"error": "SUPABASE_ANON_KEY environment variable not set"}
        
        try:
            logger.info(f"🔍 Scoping AgentKit idea: {query[:100]}...")
            
            # Prepare API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "idea": query,
                "mode": mode
            }
            print(f"payload: {payload}")
            print(f"headers: {headers}")
            print(f"api_url: {self.api_url}")
            print(f"api_key length: {len(self.api_key) if self.api_key else 0}")
            
            if project_id:
                payload["projectId"] = project_id
            
            # Call the scope-agkit-idea API
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ AgentKit idea scoped successfully")
                return result
                
            else:
                error_msg = f"API request failed: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"AgentKit idea scoping failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}

# Export tool for auto-discovery
scope_agkit_idea_tool = ScopeAgentKitIdeaTool()