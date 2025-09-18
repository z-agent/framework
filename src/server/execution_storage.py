#!/usr/bin/env python3
"""
🔥 Execution Storage Module
Store agent execution results for analytics and search
Zero breaking changes to existing code
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from qdrant_client import QdrantClient
import json
import os

class ExecutionStorage:
    """Store and retrieve agent execution results"""
    
    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
        self.collection_name = "executions"
        self._ensure_collection_exists()
    
    def _ensure_collection_exists(self):
        """Create executions collection if it doesn't exist"""
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection with proper schema
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "size": 1536,  # OpenAI embedding size
                        "distance": "Cosine"
                    }
                )
                print(f"✅ Created {self.collection_name} collection")
            else:
                print(f"✅ {self.collection_name} collection already exists")
                
        except Exception as e:
            print(f"⚠️  Collection setup warning: {e}")
    
    def store_execution(self, agent_id: str, arguments: Dict[str, Any], 
                       result: str, token_usage: Optional[Dict] = None,
                       execution_time: Optional[float] = None) -> str:
        """Store execution result"""
        try:
            execution_id = str(uuid.uuid4())
            
            execution_data = {
                "id": execution_id,
                "agent_id": agent_id,
                "query": arguments.get("query", ""),
                "result": result[:10000],  # Limit result size
                "arguments": arguments,
                "token_usage": token_usage or {},
                "execution_time": execution_time or 0.0,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
                "rating": None,
                "user_feedback": None,
                "votes": 0,
                "tags": self._extract_tags(result)
            }
            
            # Generate proper vector from result content
            try:
                # Use OpenAI embeddings if available
                import openai
                openai.api_key = os.getenv("OPENAI_API_KEY")
                if openai.api_key:
                    response = openai.Embedding.create(
                        input=result[:1000],  # Limit input for embedding
                        model="text-embedding-ada-002"
                    )
                    vector = response['data'][0]['embedding']
                else:
                    # Fallback to simple hash-based vector
                    import hashlib
                    hash_obj = hashlib.md5(result.encode())
                    hash_bytes = hash_obj.digest()
                    vector = [float(b) / 255.0 for b in hash_bytes] * 60  # Repeat to get 1536 dimensions
            except Exception as e:
                # Final fallback to simple vector
                vector = [0.1] * 1536
            
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[{
                    "id": execution_id,
                    "vector": vector,
                    "payload": execution_data
                }]
            )
            
            print(f"✅ Stored execution: {execution_id}")
            return execution_id
            
        except Exception as e:
            print(f"⚠️  Failed to store execution: {e}")
            return None
    
    def _extract_tags(self, result: str) -> list:
        """Extract tags from execution result"""
        tags = []
        result_lower = result.lower()
        
        # Crypto tags
        if any(word in result_lower for word in ["crypto", "blockchain", "defi", "tokenomics"]):
            tags.append("crypto")
        if "token" in result_lower:
            tags.append("tokenomics")
        if "defi" in result_lower:
            tags.append("defi")
        
        # Business tags
        if any(word in result_lower for word in ["startup", "business", "saas"]):
            tags.append("startup")
        if "reddit" in result_lower:
            tags.append("reddit")
        
        return tags
    
    def get_execution(self, execution_id: str) -> Optional[Dict]:
        """Get execution by ID"""
        try:
            result = self.qdrant_client.retrieve(
                collection_name=self.collection_name,
                ids=[execution_id]
            )
            return result[0].payload if result else None
        except Exception as e:
            print(f"⚠️  Failed to get execution: {e}")
            return None
    
    def list_executions(self, limit: int = 50, offset: int = 0) -> list:
        """List recent executions"""
        try:
            result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                offset=offset
            )
            return [item.payload for item in result[0]] if result[0] else []
        except Exception as e:
            print(f"⚠️  Failed to list executions: {e}")
            return []
    
    def search_executions(self, query: str, limit: int = 20) -> list:
        """Search executions by query"""
        try:
            # Simple text search for now
            all_executions = self.list_executions(limit=1000)
            query_lower = query.lower()
            
            matching = []
            for execution in all_executions:
                if (query_lower in execution.get("query", "").lower() or
                    query_lower in execution.get("result", "").lower()):
                    matching.append(execution)
            
            return matching[:limit]
        except Exception as e:
            print(f"⚠️  Failed to search executions: {e}")
            return []
    
    def rate_execution(self, execution_id: str, rating: int, feedback: str = "") -> bool:
        """Rate an execution result"""
        try:
            execution = self.get_execution(execution_id)
            if not execution:
                return False
            
            # Update rating
            execution["rating"] = rating
            execution["user_feedback"] = feedback
            
            # Update in Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[{
                    "id": execution_id,
                    "vector": [0.1] * 1536,  # Placeholder vector
                    "payload": execution
                }]
            )
            
            print(f"✅ Rated execution {execution_id}: {rating}/5")
            return True
            
        except Exception as e:
            print(f"⚠️  Failed to rate execution: {e}")
            return False
