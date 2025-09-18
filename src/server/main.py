# from src.tools.trading_tools import pumpfun_volume_tool, whale_tracker_tool
from src.tools.trading_tools import IvishXAnalyzeTool, ZApiTechnicalAnalysis, CombinedTechnicalAnalysis
from src.tools.linear_tools import LinearScopingTool, LinearPRReviewTool, LinearCodingTool, LinearProjectManagerTool
from src.tools.linear_workflow_creator import LinearWorkflowCreator
from src.tools.reddit_tool import reddit_business_intel_tool
from src.tools.saas_generator_tool import saas_generator_tool
from src.tools.solana_tools import TokenFundamentalAnalysis, TokenTechnicalAnalysis, TokenInfoTool
from src.tools.youtube_creator_tools_fixed import YOUTUBE_TOOLS_FIXED as YOUTUBE_TOOLS

# Import Telegram tools (will gracefully fail if dependencies missing)
try:
    from src.tools.telegram_reader_tool import telegram_message_reader, telegram_quick_reader
    TELEGRAM_TOOLS_AVAILABLE = True
except ImportError:
    TELEGRAM_TOOLS_AVAILABLE = False
    print("⚠️  Telegram tools not available. Run setup_telegram_reader.py to configure.")

# Import Hyperliquid tools (will gracefully fail if dependencies missing)
try:
    from src.tools.hyperliquid_tools import HYPERLIQUID_TOOLS
    HYPERLIQUID_TOOLS_AVAILABLE = True
    print("✅ Hyperliquid builder code tools loaded - Ready to earn fees!")
except ImportError as e:
    HYPERLIQUID_TOOLS_AVAILABLE = False
    print(f"⚠️  Hyperliquid tools not available: {e}")
    print("💡 Install dependencies: pip install eth-account")
    HYPERLIQUID_TOOLS = []

# Import Ship-to-Earn tools
try:
    from src.tools.ship_to_earn_dev_team import (
        ProjectManagerAgent,
        SeniorDeveloperAgent,
        QAEngineerAgent,
        DevOpsEngineerAgent,
        RevenueDistributionSystem
    )
    from src.workflows.ship_to_earn_workflow import register_ship_to_earn_workflows
    SHIP_TO_EARN_AVAILABLE = True
    print("💰 Ship-to-Earn AI dev team loaded - Ready to build and earn!")
except ImportError as e:
    SHIP_TO_EARN_AVAILABLE = False
    print(f"⚠️  Ship-to-Earn tools not available: {e}")
import uvicorn
from qdrant_client import QdrantClient
from os import environ, getenv
from dotenv import load_dotenv
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import os
import requests

load_dotenv()

from src.server.api import create_api
from src.server.registry import Registry

# Configure OpenRouter and LiteLLM
environ["OPENAI_API_KEY"] = getenv("OPENROUTER_API_KEY")
environ["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
environ["OPENAI_API_VERSION"] = "2023-05-15"  # Add API version
environ["OPENAI_ORGANIZATION"] = ""  # Empty string for OpenRouter

# Set proper headers for OpenRouter
environ["HTTP_REFERER"] = "https://agents.vistara.dev"
environ["X_TITLE"] = "Z Framework"
# Configure LiteLLM
import litellm
litellm.set_verbose = True  # Enable debug logging
litellm.drop_params = True  # Prevent API validation errors

# Create a simple WebSearch tool since crewai_tools is empty
class WebSearchTool(BaseTool):
    name: str = "WebSearch"
    description: str = "Search the internet for information using a search query"
    
    class ArgsSchema(BaseModel):
        search_query: str = Field(description="Mandatory search query you want to use to search the internet")
    
    def _run(self, search_query: str):
        try:
            # Prefer fresh results: normalize query year to current year if it contains an older year
            from datetime import datetime
            import re
            current_year = datetime.utcnow().year
            effective_query = search_query
            match = re.search(r"(19|20)\\d{2}", search_query or "")
            if match:
                try:
                    yr = int(match.group(0))
                    if yr < current_year:
                        effective_query = re.sub(r"(19|20)\\d{2}", str(current_year), search_query)
                except Exception:
                    pass
            else:
                if search_query:
                    effective_query = f"{search_query} {current_year}"

            # 1) Try Exa if available (best freshness)
            exa_key = os.getenv("EXA_API_KEY")
            if exa_key:
                try:
                    exa_resp = requests.post(
                        "https://api.exa.ai/search",
                        headers={"x-api-key": exa_key, "Content-Type": "application/json"},
                        json={"query": effective_query, "numResults": 8},
                        timeout=20,
                    )
                    exa_resp.raise_for_status()
                    exa_data = exa_resp.json() or {}
                    exa_results = exa_data.get("results") or exa_data.get("documents") or []
                    if isinstance(exa_results, list) and len(exa_results) > 0:
                        results = []
                        for item in exa_results[:8]:
                            title = item.get("title") or item.get("name")
                            link = item.get("url") or item.get("link")
                            snippet = item.get("text") or item.get("summary") or item.get("snippet")
                            if title and link:
                                results.append({"title": title, "snippet": snippet, "link": link})
                        if results:
                            return {"results": results, "success": True, "provider": "exa", "query": effective_query}
                except Exception:
                    # Fall back to Serper below
                    pass

            # 2) Fall back to Serper
            serper_key = os.getenv("SERPER_API_KEY")
            if serper_key:
                resp = requests.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    json={"q": effective_query, "num": 8},
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
                organic = data.get("organic", []) or []
                results = [
                    {
                        "title": item.get("title"),
                        "snippet": item.get("snippet") or item.get("description"),
                        "link": item.get("link") or item.get("url"),
                    }
                    for item in organic[:8]
                    if item.get("title") and (item.get("link") or item.get("url"))
                ]
                return {"results": results, "success": True, "provider": "serper", "query": effective_query}

            # 3) Final fallback when no provider configured
            return {
                "results": [
                    {
                        "title": f"Search results for: {effective_query}",
                        "snippet": "Set EXA_API_KEY or SERPER_API_KEY to enable real web search results.",
                        "link": "https://example.com",
                    }
                ],
                "success": True,
                "provider": "fallback",
                "query": effective_query,
            }
        except Exception as e:
            return {"error": f"Search failed: {str(e)}", "success": False}

def main():
    client = QdrantClient(
        host=environ["QDRANT_HOST"],
        port=int(environ["QDRANT_PORT"]),
        api_key=environ["QDRANT_API_KEY"],
        prefer_grpc=False,
        timeout=30.0,
        check_compatibility=False,
    )

    registry = Registry(client)

    # Clear existing tools to avoid conflicts
    print("🧹 Clearing existing tools from Qdrant...")
    try:
        # Delete the tools collection and recreate it
        client.delete_collection(collection_name="tools")
        client.create_collection(
            collection_name="tools",
            vectors_config={"size": 1536, "distance": "Cosine"}
        )
        print("✅ Tools collection cleared and recreated")
    except Exception as e:
        print(f"⚠️  Could not clear tools collection: {e}")

    # read from qdrant and register tools

    # TODO this will be made dynamic in the future where tools will be
    # run as their own services
    registry.register_tool("WebSearch", WebSearchTool())
    registry.register_tool("LinearWorkflowCreator", LinearWorkflowCreator(registry))
    registry.register_tool("LinearScopingTool", LinearScopingTool())
    registry.register_tool("LinearPRReviewTool", LinearPRReviewTool())
    registry.register_tool("LinearCodingTool", LinearCodingTool())
    registry.register_tool("LinearProjectManager", LinearProjectManagerTool())

    # Additional tools
    registry.register_tool("RedditBusinessIntel", reddit_business_intel_tool)
    registry.register_tool("SaaSBusinessGenerator", saas_generator_tool)
    registry.register_tool("SolanaTokenFundamentals", TokenFundamentalAnalysis())
    registry.register_tool("SolanaTokenTechnicals", TokenTechnicalAnalysis())
    registry.register_tool("SolanaTokenInfo", TokenInfoTool())
    
    # LinkedIn Lead Generation Tool
    try:
        from src.tools.linkedin_lead_generator_tool import create_linkedin_lead_generator_tool
        linkedin_tool = create_linkedin_lead_generator_tool()
        registry.register_tool("LinkedInLeadGenerator", linkedin_tool)
        print("🔗 LinkedIn Lead Generator tool registered successfully")
    except Exception as e:
        print(f"⚠️  LinkedIn Lead Generator tool registration warning: {e}")
    
    # LinkedIn Lead Generation Agent
    try:
        from src.agents.linkedin_lead_workflow import register_linkedin_lead_agent
        linkedin_agent_id = register_linkedin_lead_agent(registry)
        print(f"🤖 LinkedIn Lead Generation Agent registered with ID: {linkedin_agent_id}")
    except Exception as e:
        print(f"⚠️  LinkedIn Lead Generation Agent registration warning: {e}")
    # Trading tools
    try:
        registry.register_tool("IvishXAnalyze", IvishXAnalyzeTool())
        registry.register_tool("ZApiTechnicalAnalysis", ZApiTechnicalAnalysis())
        registry.register_tool("CombinedTechnicalAnalysis", CombinedTechnicalAnalysis())
        print("📈 Trading analysis tools registered successfully")
    except Exception as e:
        print(f"⚠️  Trading tools registration warning: {e}")
    # registry.register_tool("PumpFunVolume", pumpfun_volume_tool)
    # registry.register_tool("WhaleActivityCheck", whale_tracker_tool)
    
    # YouTube Creator Tools
    print("🎬 Registering YouTube Creator Tools...")
    for tool_name, tool_instance in YOUTUBE_TOOLS:
        try:
            registry.register_tool(tool_name, tool_instance)
            print(f"  ✅ Registered: {tool_name}")
        except ValueError as e:
            print(f"  ⚠️ Tool {tool_name} already exists: {e}")
            
    # Register Telegram tools if available
    if 'TELEGRAM_TOOLS_AVAILABLE' in globals() and TELEGRAM_TOOLS_AVAILABLE:
        print("📱 Registering Telegram tools...")
        try:
            registry.register_tool("TelegramMessageReader", telegram_message_reader)
            registry.register_tool("TelegramQuickReader", telegram_quick_reader)
            print("  ✅ Registered: Telegram message reading tools")
        except Exception as e:
            print(f"  ⚠️ Failed to register Telegram tools: {e}")
    
    # Register Hyperliquid tools if available
    if 'HYPERLIQUID_TOOLS_AVAILABLE' in globals() and HYPERLIQUID_TOOLS_AVAILABLE:
        print("💰 Registering Hyperliquid builder code tools...")
        try:
            for tool in HYPERLIQUID_TOOLS:
                registry.register_tool(tool.name, tool)
                print(f"  ✅ Registered: {tool.name}")
            print(f"  🎯 Ready to earn builder fees on Hyperliquid trades!")
        except Exception as e:
            print(f"  ⚠️ Failed to register Hyperliquid tools: {e}")
    
    # Register Ship-to-Earn tools if available
    if 'SHIP_TO_EARN_AVAILABLE' in globals() and SHIP_TO_EARN_AVAILABLE:
        print("🚀 Registering Ship-to-Earn AI development team...")
        try:
            registry.register_tool("ProjectManagerAgent", ProjectManagerAgent())
            registry.register_tool("SeniorDeveloperAgent", SeniorDeveloperAgent())
            registry.register_tool("QAEngineerAgent", QAEngineerAgent())
            registry.register_tool("DevOpsEngineerAgent", DevOpsEngineerAgent())
            registry.register_tool("RevenueDistributionSystem", RevenueDistributionSystem())
            print("  ✅ Ship-to-Earn agents registered successfully")
            
            # Register predefined workflows
            register_ship_to_earn_workflows(registry)
            print("  🎯 Ready to build software and earn revenue!")
        except Exception as e:
            print(f"  ⚠️ Failed to register Ship-to-Earn tools: {e}")
    
    # Register Scope AgentKit Idea tools
    print("🚀 Registering Scope AgentKit Idea tools...")
    try:
        from src.tools.scope_agkit_idea_tool import scope_agkit_idea_tool
        from src.agents.scope_agkit_idea_agent import register_scope_agkit_idea_agent
        
        # Register the tool
        registry.register_tool("ScopeAgentKitIdea", scope_agkit_idea_tool)
        print("  ✅ Scope AgentKit Idea tool registered")
        
        # Register the agent
        agent_id = register_scope_agkit_idea_agent(registry)
        print(f"  ✅ Scope AgentKit Idea agent registered with ID: {agent_id}")
        
    except Exception as e:
        print(f"  ⚠️ Failed to register Scope AgentKit Idea tools: {e}")

    # Debug: Print all registered tools
    print("🔧 All registered tools:")
    for tool_id, tool_uuid in registry.tool_ids.items():
        print(f"  {tool_id} -> {tool_uuid}")
        if tool_uuid in registry.tools:
            tool_instance, tool_info = registry.tools[tool_uuid]
            print(f"    Instance: {type(tool_instance)}")
            print(f"    Name: {getattr(tool_instance, 'name', 'NO_NAME')}")
            print(f"    Description: {getattr(tool_instance, 'description', 'NO_DESCRIPTION')}")

    # Create the FastAPI app
    app = create_api(registry)
    
    # Only run uvicorn if this file is run directly (not imported)
    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8000)
    
    return app

# Create the app instance for uvicorn to import
app = main()
