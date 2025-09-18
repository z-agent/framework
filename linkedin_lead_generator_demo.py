#!/usr/bin/env python3
"""
LinkedIn Lead Generator Demo
============================
Demonstrates how to use the LinkedIn Lead Generator tool in the Zara Framework.
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Add the framework to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.tools.linkedin_lead_generator_tool import LinkedInLeadGeneratorTool

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"🔗 {title}")
    print(f"{'='*60}")

def print_section(title):
    """Print a formatted section header"""
    print(f"\n📋 {title}")
    print("-" * 40)

def demo_linkedin_tool():
    """Demonstrate the LinkedIn Lead Generator tool"""
    
    print_header("LinkedIn Lead Generator Tool Demo")
    
    # Initialize the tool
    print("🚀 Initializing LinkedIn Lead Generator Tool...")
    try:
        tool = LinkedInLeadGeneratorTool()
        print("✅ Tool initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize tool: {e}")
        return
    
    # Demo 1: Research Prospects
    print_section("Demo 1: Research SaaS Founders")
    
    research_result = tool.research_prospects(
        target_industry="SaaS",
        target_title="Founder",
        target_company_size="10-50",
        max_prospects=5
    )
    
    if research_result.get("success"):
        print(f"✅ Found {research_result['prospects_found']} prospects")
        print(f"📊 Summary: {research_result['summary']}")
        
        # Show first few prospects
        prospects = research_result.get("prospects", [])
        if prospects:
            print("\n🏆 Top Prospects:")
            for i, prospect in enumerate(prospects[:3], 1):
                print(f"   {i}. {prospect['name']} at {prospect['company']}")
                print(f"      Title: {prospect['title']}")
                print(f"      Score: {prospect['qualification_score']:.2f}")
                print(f"      Email: {prospect['email'] or 'Not available'}")
                print()
    else:
        print(f"❌ Research failed: {research_result.get('error')}")
    
    # Demo 2: Get Statistics
    print_section("Demo 2: Get Prospect Statistics")
    
    stats_result = tool.get_stats()
    if stats_result.get("success"):
        print(f"📊 Total Prospects: {stats_result['total_prospects']}")
        print(f"🎯 Qualified Prospects: {stats_result['qualified_prospects']}")
        print(f"📧 With Emails: {stats_result['prospects_with_emails']}")
        print(f"⭐ Top Score: {stats_result['top_qualification_score']}")
        print(f"📈 Qualification Rate: {stats_result['qualification_rate']}%")
    else:
        print(f"❌ Stats failed: {stats_result.get('error')}")
    
    # Demo 3: Filter Prospects
    print_section("Demo 3: Filter Top Prospects")
    
    filter_result = tool.filter_prospects(
        filter_type="top",
        filter_value="all",
        limit=3
    )
    
    if filter_result.get("success"):
        print(f"✅ Found {filter_result['prospects_found']} top prospects")
        prospects = filter_result.get("prospects", [])
        for i, prospect in enumerate(prospects, 1):
            print(f"   {i}. {prospect['name']} - Score: {prospect['qualification_score']:.2f}")
    else:
        print(f"❌ Filter failed: {filter_result.get('error')}")
    
    # Demo 4: Create Outreach Sequences
    print_section("Demo 4: Create Outreach Sequences")
    
    outreach_result = tool.create_outreach_sequences(
        business_name="Zara AI Framework",
        value_proposition="AI-powered business automation and lead generation",
        problem_solved="Manual business processes and lack of AI cofounder",
        prospect_count=2
    )
    
    if outreach_result.get("success"):
        print(f"✅ Created {outreach_result['sequences_created']} outreach sequences")
        
        sequences = outreach_result.get("sequences", {})
        for prospect_url, sequence in sequences.items():
            print(f"\n👤 Prospect: {sequence['prospect_name']}")
            print(f"🔗 LinkedIn: {prospect_url}")
            print(f"📝 Connection Request: {sequence['connection_request']}")
            print(f"💬 First Message: {sequence['first_message']}")
            print(f"📈 Follow-up 1: {sequence['follow_up_1']}")
    else:
        print(f"❌ Outreach creation failed: {outreach_result.get('error')}")
    
    # Demo 5: Export Prospects
    print_section("Demo 5: Export Prospects")
    
    export_result = tool.export_prospects(format="json", filename="demo_prospects.json")
    if export_result.get("success"):
        print(f"✅ Exported {export_result['total_prospects']} prospects to {export_result['export_file']}")
    else:
        print(f"❌ Export failed: {export_result.get('error')}")
    
    print_header("Demo Complete!")
    print("🎯 The LinkedIn Lead Generator tool is ready for use!")
    print("\n📚 Available Actions:")
    print("   • research_prospects() - Find and qualify prospects")
    print("   • create_outreach_sequences() - Generate personalized outreach")
    print("   • filter_prospects() - Filter by industry, size, or top prospects")
    print("   • export_prospects() - Export to CSV or JSON")
    print("   • get_stats() - Get prospect database statistics")

def demo_api_usage():
    """Demonstrate how to use the tool via the API"""
    
    print_header("API Usage Examples")
    
    print("🌐 To use the LinkedIn Lead Generator via API:")
    print("\n1. Start the Zara Framework server:")
    print("   python src/server/main.py")
    
    print("\n2. Make API calls to the tool:")
    print("""
   # Research prospects
   curl -X POST "http://localhost:8000/tools/execute" \\
        -H "Content-Type: application/json" \\
        -d '{
            "tool_name": "LinkedInLeadGenerator",
            "action": "research",
            "target_industry": "SaaS",
            "target_title": "Founder",
            "target_company_size": "10-50",
            "max_prospects": 10
        }'
   
   # Create outreach sequences
   curl -X POST "http://localhost:8000/tools/execute" \\
        -H "Content-Type: application/json" \\
        -d '{
            "tool_name": "LinkedInLeadGenerator",
            "action": "outreach",
            "business_name": "Your Company",
            "value_proposition": "Your value prop",
            "problem_solved": "Problem you solve",
            "prospect_count": 5
        }'
   
   # Get statistics
   curl -X POST "http://localhost:8000/tools/execute" \\
        -H "Content-Type: application/json" \\
        -d '{
            "tool_name": "LinkedInLeadGenerator",
            "action": "stats"
        }'
   """)

def demo_agent_integration():
    """Demonstrate how to use the tool in an agent"""
    
    print_header("Agent Integration Example")
    
    print("🤖 To use the LinkedIn Lead Generator in an agent:")
    print("""
from crewai import Agent, Task, Crew
from src.tools.linkedin_lead_generator_tool import LinkedInLeadGeneratorTool

# Create the tool
linkedin_tool = LinkedInLeadGeneratorTool()

# Create a sales agent
sales_agent = Agent(
    role="B2B Sales Specialist",
    goal="Generate qualified leads and create outreach sequences",
    backstory="Expert in B2B sales and LinkedIn lead generation",
    tools=[linkedin_tool],
    verbose=True
)

# Create a lead generation task
lead_task = Task(
    description="Research 20 SaaS founders at companies with 10-50 employees. Create personalized outreach sequences for the top 5 prospects. Export the results to CSV for the sales team.",
    agent=sales_agent,
    expected_output="A CSV file with qualified prospects and their outreach sequences"
)

# Create and run the crew
crew = Crew(
    agents=[sales_agent],
    tasks=[lead_task],
    verbose=True
)

result = crew.kickoff()
""")

def main():
    """Main demo function"""
    print("🔗 LinkedIn Lead Generator Tool Demo")
    print("=" * 50)
    
    print("\nChoose a demo:")
    print("1. Tool functionality demo")
    print("2. API usage examples")
    print("3. Agent integration example")
    print("4. Run all demos")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        demo_linkedin_tool()
    elif choice == "2":
        demo_api_usage()
    elif choice == "3":
        demo_agent_integration()
    elif choice == "4":
        demo_linkedin_tool()
        demo_api_usage()
        demo_agent_integration()
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
