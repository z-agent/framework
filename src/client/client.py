import json
import requests


def main():
    base = "http://localhost:8000"
    # Fetch the relevant tool
    tools = requests.get(base + "/tool_search?query=serper").json()
    print(tools[0])

    # Define the agent workflow
    agents_config = {
        "researcher": {
            "role": "{topic} Senior Data Researcher",
            "goal": "Uncover cutting-edge developments in {topic}",
            "backstory": """You're a seasoned researcher with a knack for uncovering the latest developments \
    in {topic}. Known for your ability to find the most relevant \
    information and present it in a clear and concise manner.""",
            # We must pass the tool by id
            "agent_tools": [tools[0]["id"]],
        },
        "reporting_analyst": {
            "role": "{topic} Reporting Analyst",
            "goal": "Create detailed reports based on {topic} data analysis and research findings",
            "backstory": """You're a meticulous analyst with a keen eye for detail. You're known for \
    your ability to turn complex data into clear and concise reports, making \
    it easy for others to understand and act on the information you provide.""",
            "agent_tools": [],
        },
    }
    tasks_config = {
        "research_task": {
            "description": """Conduct a thorough research about {topic} \
Make sure you find any interesting and relevant information given \
the current year is 2024.""",
            "expected_output": "A list with 10 bullet points of the most relevant information about {topic}",
            "agent": "researcher",
        },
        "reporting_task": {
            "description": """Review the context you got and expand each topic into a full section for a report. \
Make sure the report is detailed and contains any and all relevant information.""",
            "expected_output": "A fully fledge reports with the mains topics, each with a full section of information. Formatted as markdown without '```'",
            "agent": "reporting_analyst",
        },
    }

    agent = requests.post(
        base + "/save_agent",
        json={
            "name": "Researcher Agent",
            "description": "Agent to research and summarize any given topic",
            "arguments": ["topic"],
            "agents": agents_config,
            "tasks": tasks_config,
        },
    ).json()

    print("Saved agent with ID", agent["agent_id"])

    response = requests.get(
        base + "/agent_call?agent_id=" + agent["agent_id"],
        json={
            "topic": "AI Agents",
        },
    ).json()
    print(response)


main()
