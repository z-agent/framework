#!/usr/bin/env python3
"""
LinkedIn Lead Generation Agent Demo
==================================
Demonstrates how to use the LinkedIn Lead Generation Agent with natural language
queries, Apollo.io integration, and flexible response formatting.
"""

import os
import sys
import json
import asyncio
import requests
from datetime import datetime

# Add the framework to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*70}")
    print(f"🔗 {title}")
    print(f"{'='*70}")

def print_section(title):
    """Print a formatted section header"""
    print(f"\n📋 {title}")
    print("-" * 50)

def test_agent_directly():
    """Test the LinkedIn agent directly (without API)"""
    print_header("Direct Agent Testing")
    
    try:
        from src.agents.linkedin_lead_agent import linkedin_agent
        
        # Test queries
        test_queries = [
            "Find 5 SaaS founders at companies with 10-50 employees",
            "Research fintech CEOs and create outreach sequences in markdown format",
            "Get me 3 CTOs from healthcare startups in table format"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print_section(f"Test Query {i}")
            print(f"Query: {query}")
            
            # Test the agent
            result = asyncio.run(linkedin_agent.handle_request(query))
            
            if result.get("success"):
                print(f"✅ Success!")
                print(f"📊 Prospects found: {result['results']['prospects_found']}")
                print(f"🎯 Qualified: {result['results']['qualified_prospects']}")
                print(f"📧 With emails: {result['results']['with_emails']}")
                print(f"💬 Outreach sequences: {result['results']['outreach_sequences']}")
                
                # Show a sample of the formatted response
                formatted = result.get('formatted_response', '')
                if formatted:
                    print(f"\n📄 Sample Response ({len(formatted)} chars):")
                    print(formatted[:200] + "..." if len(formatted) > 200 else formatted)
            else:
                print(f"❌ Failed: {result.get('error')}")
            
            print()
    
    except Exception as e:
        print(f"❌ Direct testing failed: {e}")
        import traceback
        traceback.print_exc()

def test_via_api():
    """Test the LinkedIn agent via API"""
    print_header("API Testing")
    
    # Test queries with different formats
    test_cases = [
        {
            "name": "Basic SaaS Founders Query",
            "query": "Find 10 SaaS founders at companies with 10-50 employees",
            "context": {
                "business_name": "AI Solutions Inc",
                "value_proposition": "AI-powered business automation",
                "problem_solved": "Manual business processes"
            }
        },
        {
            "name": "Fintech CEOs with Outreach (Markdown)",
            "query": "Research fintech CEOs and create outreach sequences in markdown format",
            "context": {
                "business_name": "FinTech Pro",
                "value_proposition": "Advanced financial analytics",
                "problem_solved": "Outdated financial reporting"
            }
        },
        {
            "name": "Healthcare CTOs (Table Format)",
            "query": "Get me 5 CTOs from healthcare startups in table format",
            "context": {
                "business_name": "HealthTech Solutions",
                "value_proposition": "Healthcare data integration",
                "problem_solved": "Fragmented healthcare data"
            }
        }
    ]
    
    print("🚀 Starting API tests...")
    print("Note: Make sure the framework server is running on localhost:8000")
    
    for i, test_case in enumerate(test_cases, 1):
        print_section(f"API Test {i}: {test_case['name']}")
        
        try:
            # First, we need to get the agent ID
            # For demo purposes, we'll assume the agent is already registered
            # In practice, you'd get this from the /save_agent response
            
            print(f"Query: {test_case['query']}")
            print(f"Context: {test_case['context']}")
            
            # This would be the actual API call
            print("📡 API Call would be:")
            print(f"""
curl -X POST "http://localhost:8000/agent_call?agent_id=YOUR_AGENT_ID" \\
     -H "Content-Type: application/json" \\
     -d '{{
         "query": "{test_case['query']}",
         "context": {json.dumps(test_case['context'])}
     }}'
""")
            
            print("✅ API call structure prepared")
            
        except Exception as e:
            print(f"❌ API test failed: {e}")

def demo_natural_language_parsing():
    """Demonstrate natural language parsing capabilities"""
    print_header("Natural Language Parsing Demo")
    
    try:
        from src.agents.linkedin_lead_agent import linkedin_agent
        
        # Test various natural language queries
        test_queries = [
            "Find 20 SaaS founders at companies with 10-50 employees",
            "Research fintech CEOs and create outreach sequences in markdown format",
            "Get me 10 CTOs from healthcare startups in table format",
            "I need 5 VP Sales from ecommerce companies with 50-200 employees",
            "Find AI startup founders and create personalized messages",
            "Research cybersecurity directors at enterprise companies",
            "Get me 15 edtech CEOs in JSON format with outreach sequences"
        ]
        
        print("🧠 Testing natural language parsing...")
        
        for query in test_queries:
            print(f"\n📝 Query: {query}")
            
            # Parse the query
            request = linkedin_agent.parse_natural_language_request(query)
            
            print(f"   Industry: {request.industry}")
            print(f"   Title: {request.title}")
            print(f"   Company Size: {request.company_size}")
            print(f"   Max Prospects: {request.max_prospects}")
            print(f"   Response Format: {request.response_format}")
            print(f"   Include Outreach: {request.include_outreach}")
    
    except Exception as e:
        print(f"❌ Natural language parsing demo failed: {e}")

def demo_response_formats():
    """Demonstrate different response formats"""
    print_header("Response Format Demo")
    
    try:
        from src.agents.linkedin_lead_agent import linkedin_agent
        
        # Test different format requests
        format_tests = [
            {
                "query": "Find 3 SaaS founders in JSON format",
                "format": "json"
            },
            {
                "query": "Research 2 fintech CEOs in markdown format",
                "format": "markdown"
            },
            {
                "query": "Get 2 healthcare CTOs in table format",
                "format": "table"
            }
        ]
        
        for test in format_tests:
            print_section(f"Testing {test['format'].upper()} format")
            print(f"Query: {test['query']}")
            
            # Parse and show what format would be used
            request = linkedin_agent.parse_natural_language_request(test['query'])
            print(f"Detected format: {request.response_format}")
            
            if request.response_format == test['format']:
                print("✅ Format detection correct")
            else:
                print(f"⚠️  Expected {test['format']}, got {request.response_format}")
    
    except Exception as e:
        print(f"❌ Response format demo failed: {e}")

def show_usage_examples():
    """Show comprehensive usage examples"""
    print_header("Usage Examples")
    
    print("""
🎯 LinkedIn Lead Generation Agent Usage Examples

1. BASIC LEAD GENERATION:
   Query: "Find 20 SaaS founders at companies with 10-50 employees"
   Response: JSON with prospect details, qualification scores, contact info

2. WITH OUTREACH SEQUENCES:
   Query: "Research fintech CEOs and create outreach sequences in markdown format"
   Response: Markdown report with prospects + personalized LinkedIn messages

3. TABLE FORMAT:
   Query: "Get me 10 CTOs from healthcare startups in table format"
   Response: Clean table with key prospect information

4. WITH BUSINESS CONTEXT:
   Query: "Find 15 AI startup founders and create personalized messages"
   Context: {
     "business_name": "AI Solutions Inc",
     "value_proposition": "AI-powered automation",
     "problem_solved": "Manual business processes"
   }
   Response: Prospects + personalized outreach sequences

5. ENTERPRISE FOCUS:
   Query: "Research cybersecurity directors at enterprise companies"
   Response: High-level prospects from large companies

6. SPECIFIC INDUSTRIES:
   Query: "Get me 5 VP Sales from ecommerce companies with 50-200 employees"
   Response: Targeted prospects from specific industry and company size

🔧 API USAGE:

1. Register Agent:
   POST /save_agent
   {
     "name": "LinkedIn Lead Generation Agent",
     "description": "Advanced LinkedIn lead generation...",
     "arguments": ["query", "context"],
     "agents": {...},
     "tasks": {...}
   }

2. Call Agent:
   POST /agent_call?agent_id=YOUR_AGENT_ID
   {
     "query": "Find 10 SaaS founders at companies with 10-50 employees",
     "context": {
       "business_name": "Your Company",
       "value_proposition": "Your value prop",
       "problem_solved": "Problem you solve"
     }
   }

3. Response Formats:
   - JSON: Structured data for programmatic use
   - Markdown: Human-readable reports
   - Table: Clean tabular format for scanning

🎯 KEY FEATURES:
   - Natural language query parsing
   - Apollo.io integration for real data
   - AI-powered prospect qualification
   - Personalized outreach sequence generation
   - Multiple response formats
   - Business context awareness
   - Industry and company size filtering
""")

def main():
    """Main demo function"""
    print("🔗 LinkedIn Lead Generation Agent Demo")
    print("=" * 50)
    
    print("\nChoose a demo:")
    print("1. Direct agent testing (no API)")
    print("2. API testing examples")
    print("3. Natural language parsing demo")
    print("4. Response format demo")
    print("5. Usage examples")
    print("6. Run all demos")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == "1":
        test_agent_directly()
    elif choice == "2":
        test_via_api()
    elif choice == "3":
        demo_natural_language_parsing()
    elif choice == "4":
        demo_response_formats()
    elif choice == "5":
        show_usage_examples()
    elif choice == "6":
        test_agent_directly()
        test_via_api()
        demo_natural_language_parsing()
        demo_response_formats()
        show_usage_examples()
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
