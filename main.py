import os
from crewai import Agent, Task, Crew

# Importing crewAI tools
from crewai_tools import (
    DirectoryReadTool,
    FileReadTool,
    SerperDevTool,
    WebsiteSearchTool,
)
from src import registry, virtual_tool

# Instantiate tools
registry.register_tool(
    "DirectoryReadTool", DirectoryReadTool(directory="./blog-posts")
)
registry.register_tool("FileReadTool", FileReadTool())
registry.register_tool("SerperDevTool", SerperDevTool())
registry.register_tool("WebsiteSearchTool", WebsiteSearchTool())

# Create agents
researcher = Agent(
    role="Market Research Analyst",
    goal="Provide up-to-date market analysis of the AI industry",
    backstory="An expert analyst with a keen eye for market trends.",
    # tools=[SerperDevTool(), WebsiteSearchTool()],
    tools=[
        virtual_tool.get_virtual_tool("SerperDevTool"),
        virtual_tool.get_virtual_tool("WebsiteSearchTool"),
    ],
    verbose=True,
)

writer = Agent(
    role="Content Writer",
    goal="Craft engaging blog posts about the AI industry",
    backstory="A skilled writer with a passion for technology.",
    # tools=[DirectoryReadTool(directory='./blog-posts'), FileReadTool()],
    tools=[
        virtual_tool.get_virtual_tool("DirectoryReadTool"),
        virtual_tool.get_virtual_tool("FileReadTool"),
    ],
    verbose=True,
)

# Define tasks
research = Task(
    description="Research the latest trends in the AI industry and provide a summary.",
    expected_output="A summary of the top 3 trending developments in the AI industry with a unique perspective on their significance.",
    agent=researcher,
)

write = Task(
    description="Write an engaging blog post about the AI industry, based on the research analyst’s summary. Draw inspiration from the latest blog posts in the directory.",
    expected_output="A 4-paragraph blog post formatted in markdown with engaging, informative, and accessible content, avoiding complex jargon.",
    agent=writer,
    output_file="blog-posts/new_post.md",  # The final blog post will be saved here
)

# Assemble a crew with planning enabled
crew = Crew(
    agents=[researcher, writer],
    tasks=[research, write],
    verbose=True,
    planning=True,  # Enable planning feature
)

# Execute tasks
crew.kickoff()
