import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import supabase
from rich.console import Console
from rich.panel import Panel

# Initialize console for rich output
console = Console()

# Load environment variables
load_dotenv()

# Configure OpenRouter
os.environ["OPENAI_API_KEY"] = os.getenv("OPENROUTER_API_KEY")
os.environ["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"

class MindshareSchema(BaseModel):
    token_symbol: str = Field(
        ..., description="Name of token for fetching mindshare analysis"
    )

class MindshareTool(BaseTool):
    name: str = "Fetch mindshare data for a token"
    description: str = "A tool to fetch mindshare data"
    args_schema: Type[BaseModel] = MindshareSchema
    _supabase_client: supabase.Client

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._supabase_client = supabase.create_client(
            os.environ["SUPABASE_URL"], 
            os.environ["SUPABASE_KEY"]
        )

    def _run(self, **kwargs):
        rows = (
            self._supabase_client.table("mindshare_analysis")
            .select("*")
            .eq("token_symbol", kwargs["token_symbol"])
            .execute()
        )
        return rows.data[0]

class MindshareCrew:
    def agent(self) -> Agent:
        return Agent(
            role="Token mindshare analyst",
            goal="Analyze mindshare for tokens based on various parameters",
            backstory="""\
You can analyze a token's mindshare based on various metrics:

| Metric | Description |
|--------|-------------|
| mention_velocity | Rate of change in social mentions over time |
| engagement_ratio | Engagement per mention, showing quality of interactions |
| sentiment_score | Average sentiment of mentions (-1 to 1) |
| attention_score | Relative attention compared to peers (0-1) |
| narrative_strength | Consistency of messaging and theme (0-1) |
| social_momentum | Rate of growing social activity (velocity) |
| price_sentiment_correlation | Relationship between price movement and sentiment (-1 to 1) |
| bull_bear_ratio | Ratio of positive to negative sentiment mentions |
| viral_impact | Measure of content virality and spread |
| mindshare_strength | Overall mindshare measurement (0-100) |
| engagement_quality | Quality of interactions (0-1) |
            """,
            tools=[MindshareTool()],
            verbose=True,
        )

    def task(self) -> Task:
        return Task(
            description="Analyze the given token",
            expected_output="""\
RULES:
1. Write exactly 3 short, punchy sentences
2. Focus on actionable insights
3. Include specific numbers/levels
4. Match technical analysis style
5. No bullet points or sections

Your task:
Provide 3 actionable insights for {token} based on social attention and mindshare data:
- Correlate key metrics (price, volume, engagement_quality, mindshare_strength, price_sentiment_correlation) with price action
- Highlight specific events driving momentum or reversals

Focus on:
- The most interesting patterns you see
- Time-sensitive opportunities
- Clear connections between social signals and potential price moves
- Specific numbers and levels that matter, non-zero

Style Guide:
- Write like you're sharing alpha with fellow traders
- Be conversational but concise and sharp
- Let the story flow naturally

IMPORTANT: Up to 4 sentences maximum. Focus on what's most actionable and interesting. No fluff, no filler, just the alpha that matters right now.

IMPORTANT: ONLY REPLY with the response text, nothing else. NO titles, NO EMOJIS, NO HASHTAGS, NO disclaimers.
            """,
            agent=self.agent(),
        )

    def crew(self) -> Crew:
        return Crew(
            agents=[self.agent()],
            tasks=[self.task()],
            process=Process.sequential,
            verbose=True,
        )

def run_demo():
    """Run the mindshare analysis demo"""
    
    console.print(Panel.fit(
        "🚀 Mindshare Analysis Demo",
        style="bold blue"
    ))
    
    # Get token input
    token = console.input("[bold green]Enter token to analyze (e.g., BTC, ETH, ZARA): [/bold green]")
    if not token:
        token = "ZARA"
    
    console.print(f"\n[bold]Analyzing {token}...[/bold]")
    
    # Run analysis
    result = MindshareCrew().crew().kickoff(inputs={"token": token})
    
    # Extract raw text from CrewOutput
    analysis_text = result.raw if hasattr(result, 'raw') else str(result)
    
    # Display results
    console.print("\n[bold green]✅ Analysis Complete![/bold green]")
    console.print(Panel(analysis_text, title=f"{token} Mindshare Analysis", style="cyan"))

if __name__ == "__main__":
    run_demo() 