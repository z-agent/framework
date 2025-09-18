#!/usr/bin/env python3
"""
🔥 SAAS BUSINESS GENERATOR TOOL
Transform market pain points into complete SaaS business plans
Uses LLM to intelligently analyze market data and generate concepts
"""

import json
import time
from typing import Dict, Any, List
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
import openai
from os import getenv

class SaaSGeneratorSchema(BaseModel):
    """Schema for SaaS business generation"""
    market_data: str = Field(..., description="Market research data, pain points, or audience insights")
    target_audience: str = Field(default="general", description="Target audience or market segment")
    complexity_level: str = Field(default="mvp", description="Complexity level: mvp, intermediate, advanced")

class SaaSBusinessGeneratorTool(BaseTool):
    """Generate complete SaaS business plans from market insights using LLM"""
    name: str = "SaaS Business Generator"
    description: str = "Transform market pain points into complete SaaS business plans with MVP scope, monetization, and GTM strategy"
    args_schema: type = SaaSGeneratorSchema

    def _run(self, **kwargs) -> Dict[str, Any]:
        market_data = kwargs.get("market_data", "")
        target_audience = kwargs.get("target_audience", "general")
        complexity_level = kwargs.get("complexity_level", "mvp")
        
        # Handle empty inputs - check for query parameter as fallback
        if not market_data or market_data.strip() == "":
            # Check for context from previous tasks
            context = kwargs.get("context", {})
            previous_results = kwargs.get("previous_results", [])
            query = kwargs.get("query", "")
            
            print(f"🔍 No direct market_data, checking context: {len(context)} items, previous_results: {len(previous_results)} items")
            
            # Extract market data from context or previous results
            extracted_data = ""
            for result in previous_results:
                if isinstance(result, dict) and "posts" in str(result):
                    extracted_data = str(result)
                    print(f"📊 Extracted Reddit data from previous results: {len(extracted_data)} chars")
                    break
            
            if extracted_data:
                market_data = extracted_data
            elif query and query.strip():
                print(f"⚠️ Using 'query' parameter as market_data: {query}")
                market_data = f"Market research needed for: {query}"
            else:
                print("⚠️ No market data found anywhere, generating generic business concepts")
                market_data = "general market opportunities and pain points in productivity and business tools"
        
        try:
            print(f"🚀 Generating SaaS business ideas from market data: {market_data[:100]}...")
            
            # Use LLM to extract pain points and generate concepts
            concepts = self._generate_concepts_with_llm(market_data, target_audience, complexity_level)
            
            # Return the concepts directly as the main response
            # This prevents the agent from reformatting the JSON into markdown
            return {
                "status": "success",
                "concepts": concepts,  # Raw JSON concepts here
                "saas_concepts": concepts,  # For backward compatibility
                "concepts_count": len(concepts),
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "market_analysis": {
                    "target_audience": target_audience,
                    "identified_pain_points": len(concepts),
                    "market_size_estimate": self._estimate_market_size(target_audience),
                    "complexity_level": complexity_level
                },
                "top_recommendation": concepts[0] if concepts else None,
                "launch_readiness": "High - Ready for validation" if concepts else "Low - No concepts generated",
                "next_steps": self._generate_next_steps(concepts[0] if concepts else None),
                "success": True,
                # Add raw JSON string for easy parsing
                "raw_json": json.dumps(concepts, indent=2) if concepts else "[]"
            }
            
        except Exception as e:
            print(f"Error in SaaS generator: {e}")
            return {
                "status": "error", 
                "error": f"Failed to generate SaaS concepts: {str(e)}", 
                "success": False,
                "concepts": [],
                "raw_json": "[]"
            }

    def _generate_concepts_with_llm(self, market_data: str, target_audience: str, complexity_level: str) -> List[Dict[str, Any]]:
        """Use LLM to generate SaaS concepts from market data"""
        
        # Configure OpenAI client
        client = openai.OpenAI(
            api_key=getenv("OPENROUTER_API_KEY") or getenv("OPENAI_API_KEY"),
            base_url="https://openrouter.ai/api/v1" if getenv("OPENROUTER_API_KEY") else "https://api.openai.com/v1"
        )
        
        prompt = f"""
Analyze this market research data and generate exactly 3 unique SaaS business concepts:

MARKET DATA:
{market_data}

TARGET AUDIENCE: {target_audience}
COMPLEXITY: {complexity_level}

Generate 3 completely different SaaS apps that solve real problems from this data. 

Return a complete app specification as valid JSON in the following format:
[
  {{
    "appName": "Name of the app",
    "tagline": "One-line description",
    "appPurpose": "A short, clear description of what problem it solves",
    "businessModel": {{
      "type": "Subscription|Freemium|One-time purchase|etc",
      "pricing": "Pricing strategy details",
      "justification": "Why users would pay for this"
    }},
    "coreFeatures": [
      {{
        "name": "Feature name",
        "description": "What it does",
        "painPointAddressed": "Pain point it solves",
        "valueProposition": "How it helps users or generates value"
      }}
    ],
    "technicalSpecs": {{
      "dataModel": [
        {{
          "entity": "User|Product|etc",
          "attributes": ["attribute1", "attribute2"],
          "relationships": ["relates to other entities"]
        }}
      ],
      "apiRequirements": [
        {{
          "name": "API name",
          "purpose": "What it's used for",
          "endpoint": "Specific endpoint if known"
        }}
      ],
      "userFlows": [
        {{
          "name": "User flow name",
          "steps": ["Step 1", "Step 2"]
        }}
      ]
    }}
  }}
]

Response MUST be valid JSON matching the schema exactly. Focus on real, actionable problems from the market data. Make each app distinct and valuable.
"""

        try:
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",  # Use a reliable model
                messages=[
                    {"role": "system", "content": "You are a startup advisor who creates viable SaaS business plans. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            # Parse the LLM response
            content = response.choices[0].message.content
            
            # Extract JSON from the response
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_content = content[json_start:json_end].strip()
            else:
                # Try to find JSON array directly
                start = content.find("[")
                end = content.rfind("]") + 1
                json_content = content[start:end] if start != -1 and end != 0 else content
            
            # Parse and validate JSON
            concepts = json.loads(json_content)
            
            if isinstance(concepts, list) and len(concepts) > 0:
                print(f"✅ Generated {len(concepts)} SaaS concepts using LLM")
                return concepts
            else:
                print("⚠️ LLM returned invalid format, using fallback")
                return self._create_fallback_concepts(market_data, target_audience)
                
        except Exception as e:
            print(f"⚠️ LLM generation failed: {e}, using fallback")
            return self._create_fallback_concepts(market_data, target_audience)

    def _create_fallback_concepts(self, market_data: str, target_audience: str) -> List[Dict[str, Any]]:
        """Create fallback concepts when LLM fails"""
        return [
            {
                "appName": "MarketSolver",
                "tagline": "Turn market insights into actionable solutions",
                "appPurpose": "Helps businesses analyze market feedback and convert insights into product improvements and new opportunities",
                "businessModel": {
                    "type": "Subscription",
                    "pricing": "Pro: $49/month, Enterprise: $199/month",
                    "justification": "Saves companies thousands in market research costs and accelerates product development cycles"
                },
                "coreFeatures": [
                    {
                        "name": "Market Analysis Dashboard",
                        "description": "Visualizes market trends and user feedback patterns",
                        "painPointAddressed": "Difficulty understanding market signals",
                        "valueProposition": "Reduces analysis time from weeks to hours"
                    },
                    {
                        "name": "Insight Extraction Engine",
                        "description": "Automatically identifies key pain points from market data",
                        "painPointAddressed": "Manual analysis is time-consuming and error-prone",
                        "valueProposition": "AI-powered extraction with 90% accuracy"
                    },
                    {
                        "name": "Action Recommendations",
                        "description": "Suggests specific product improvements and new features",
                        "painPointAddressed": "Knowing what to do with insights",
                        "valueProposition": "Prioritized, actionable roadmap generation"
                    }
                ],
                "technicalSpecs": {
                    "dataModel": [
                        {
                            "entity": "User",
                            "attributes": ["id", "email", "company", "subscription_tier"],
                            "relationships": ["has many projects", "belongs to company"]
                        },
                        {
                            "entity": "MarketData",
                            "attributes": ["source", "content", "timestamp", "sentiment"],
                            "relationships": ["belongs to project", "has many insights"]
                        }
                    ],
                    "apiRequirements": [
                        {
                            "name": "Reddit API",
                            "purpose": "Fetch market discussions and feedback",
                            "endpoint": "https://www.reddit.com/r/{subreddit}/top.json"
                        },
                        {
                            "name": "OpenAI API",
                            "purpose": "Process and analyze market data with AI",
                            "endpoint": "https://api.openai.com/v1/chat/completions"
                        }
                    ],
                    "userFlows": [
                        {
                            "name": "Market Analysis Flow",
                            "steps": ["Connect data sources", "AI processes data", "Review insights", "Generate action plan", "Export results"]
                        }
                    ]
                }
            }
        ]

    def _estimate_market_size(self, target_audience: str) -> str:
        """Estimate market size based on audience"""
        if "business" in target_audience.lower() or "enterprise" in target_audience.lower():
            return "$50M - $500M (B2B)"
        elif "consumer" in target_audience.lower() or "personal" in target_audience.lower():
            return "$100M - $1B (B2C)"
        else:
            return "$10M - $100M (Niche)"

    def _generate_next_steps(self, top_concept: Dict) -> List[str]:
        """Generate next steps for the top concept"""
        if not top_concept:
            return ["Analyze market data more thoroughly", "Identify clear pain points", "Define target audience"]
        
        app_name = top_concept.get("app_name", "the concept")
        return [
            f"Validate {app_name} with 50+ target users",
            "Create landing page and collect signups",
            "Build wireframes and user flows",
            "Set up development environment",
            "Plan MVP development sprint",
            "Prepare go-to-market campaign"
        ]

# Export for registration
saas_generator_tool = SaaSBusinessGeneratorTool() 