"""
Research Agents for Social Media and Coin Analysis
Implements agents for summarizing social content and analyzing crypto projects
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from pydantic import BaseModel
from openai import OpenAI
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import os
import json
import httpx

from src.core.llm_intent_service import LLMIntentService
from src.core.market_data import MarketDataService, PerplexityClient
from src.utils.rate_limiter import rate_limiter
from src.utils.cache_manager import cache_manager
from .market_data_agent import MarketDataAgent, MarketMetrics
from .social_data_agent import SocialDataAgent, SocialMetrics

logger = logging.getLogger(__name__)

# Initialize x.ai client
xai_client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

class SocialContent(BaseModel):
    """Model for social media content"""
    platform: str
    content_type: str
    content: str
    engagement: Dict[str, int]
    timestamp: datetime
    url: str
    author: str
    media: Optional[List[str]] = None
    analysis: Optional[Dict[str, Any]] = None

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Convert to dictionary for easy access"""
        return {
            "platform": self.platform,
            "content_type": self.content_type,
            "content": self.content,
            "engagement": self.engagement,
            "timestamp": self.timestamp,
            "url": self.url,
            "author": self.author,
            "media": self.media,
            "analysis": self.analysis
        }

class ResearchSummary(BaseModel):
    """Model for research summaries"""
    topics: List[str]
    key_insights: List[str]
    sentiment: float
    sources: List[str]
    timestamp: datetime
    top_influencers: List[Dict[str, Any]]

class CoinResearch(BaseModel):
    """Model for coin research"""
    token_symbol: str
    business_model: Dict[str, Any]
    team_analysis: Dict[str, Any]
    tokenomics: Dict[str, Any]
    risk_factors: List[Dict[str, Any]]
    social_metrics: Dict[str, Any]
    market_metrics: Optional[MarketMetrics] = None
    sources: List[str]
    timestamp: datetime

class ResearchSummaryAgent:
    """Agent for summarizing social media research"""
    
    def __init__(self):
        """Initialize the research summary agent with x.ai integration."""
        self.xai_client = OpenAI(
            api_key=os.getenv("XAI_API_KEY"),
            base_url="https://api.x.ai/v1"
        )
        self.model = os.getenv("XAI_MODEL", "grok-2-latest")
        self.cache = cache_manager
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.market_data = MarketDataAgent()
        self.social_data = SocialDataAgent()
        
    async def start(self):
        """Start agent services"""
        await self.social_data.start()
        
    async def close(self):
        """Close agent services"""
        await self.market_data.close()
        await self.social_data.close()
        
    async def get_trending_topics(self, categories=None, limit=10):
        """Get trending topics using x.ai's chat completion API."""
        if not categories:
            categories = ["crypto", "ai", "blockchain", "defi", "metaverse"]
            
        cache_key = f"trending_topics_{'-'.join(categories)}_{limit}"
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            prompt = f"Analyze trending topics in the following categories: {', '.join(categories)}. Provide the top {limit} topics with their sentiment and volume metrics."
            
            completion = self.xai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research assistant specialized in analyzing crypto, blockchain, and technology trends."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                stream=False,
                max_tokens=1000
            )
            
            response = completion.choices[0].message.content
            
            # Process and structure the response
            topics = []
            for category in categories:
                topics.extend({
                    "category": category,
                    "topic": topic.strip(),
                    "sentiment": self.sentiment_analyzer.polarity_scores(topic)["compound"],
                    "volume": 0  # Default volume
                } for topic in response.split("\n") if topic.strip())
                
            await self.cache.set(cache_key, topics, ttl=3600)  # Cache for 1 hour
            return topics
            
        except Exception as e:
            logger.error(f"Error fetching trending topics: {str(e)}")
            return []
            
    async def analyze_meta_attention(self, topics):
        """Analyze meta attention patterns using x.ai."""
        try:
            topics_str = "\n".join([f"- {t['topic']} ({t['category']})" for t in topics])
            prompt = f"Analyze the following topics for meta attention patterns and cross-category trends:\n{topics_str}"
            
            response = self.xai_client.chat.completions.create(
                model="grok-2-latest",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research assistant specialized in analyzing meta attention patterns and trends across categories."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                stream=False,
                max_tokens=1000
            )
            
            return {
                "cross_category_trends": response.choices[0].message.content,
                "attention_score": 0.0  # Default score
            }
            
        except Exception as e:
            logger.error(f"Error analyzing meta attention: {str(e)}")
            return {"cross_category_trends": "", "attention_score": 0.0}
            
    async def collect_social_content(self, topic, days_back=7):
        """Collect and analyze social media content."""
        try:
            prompt = f"Analyze social media content about {topic} from the last {days_back} days. Include Twitter, Discord, and Telegram discussions."
            
            completion = self.xai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a social media analyst specialized in crypto and blockchain discussions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                stream=False,
                max_tokens=1500
            )
            
            response = completion.choices[0].message.content
            print(f"Response collecting social content: {response}")
            # Parse the content into structured format
            content_items = []
            for line in response.split("\n"):
                if line.strip():
                    content_items.append({
                        "platform": "mixed",
                        "content": line.strip(),
                        "sentiment": self.sentiment_analyzer.polarity_scores(line)["compound"],
                        "timestamp": datetime.now().isoformat()
                    })
            
            return content_items
            
        except Exception as e:
            logger.error(f"Error collecting social content: {str(e)}")
            return []
            
    async def scan_top_tweets(self, topics: List[str], min_engagement: int = 100) -> List[SocialContent]:
        """Scan and analyze top tweets for given topics."""
        try:
            topics_str = ", ".join(topics)
            prompt = f"Find and analyze top tweets about these topics: {topics_str}. Focus on posts with at least {min_engagement} engagements."
            
            completion = self.xai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a social media analyst focused on crypto Twitter."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                stream=False,
                max_tokens=1500
            )
            
            response = completion.choices[0].message.content
            
            # Parse tweets into structured format
            tweets = []
            for line in response.split("\n"):
                if line.strip():
                    tweets.append(SocialContent(
                        platform="twitter",
                        content_type="tweet",
                        content=line.strip(),
                        engagement={"likes": min_engagement, "retweets": 0},
                        timestamp=datetime.now(),
                        url="",  # Would be populated with actual URL in production
                        author="",  # Would be populated with actual author in production
                    ))
            
            return tweets
            
        except Exception as e:
            logger.error(f"Error scanning tweets: {str(e)}")
            return []
            
    def _parse_topics_from_analysis(self, analysis: str) -> List[Dict[str, Any]]:
        """Parse topics from x.ai analysis"""
        try:
            response = self.xai_client.chat.completions.create(
                model="grok-2-latest",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research assistant specialized in structuring and formatting analysis data."
                    },
                    {
                        "role": "user",
                        "content": f"Convert this analysis into structured topics with metrics:\n\n{analysis}"
                    }
                ],
                temperature=0.1,
                stream=False
            )
            
            structured = response.choices[0].message.content
            
            # Convert to Python objects (assuming JSON-like format in the response)
            try:
                return json.loads(structured)
            except:
                # Fallback to basic parsing if JSON fails
                topics = []
                for line in structured.split("\n"):
                    if ":" in line:
                        topic, rest = line.split(":", 1)
                        topics.append({
                            "topic": topic.strip(),
                            "details": rest.strip()
                        })
                return topics
                
        except Exception as e:
            logger.error(f"Error parsing topics: {str(e)}")
            return []
            
    def _parse_meta_analysis(self, analysis: str) -> Dict[str, Any]:
        """Parse meta analysis from x.ai output"""
        try:
            # Use x.ai to structure the analysis
            response = self.xai_client.chat.completions.create(
                model=os.getenv("XAI_MODEL", "grok-1"),
                messages=[{"role": "user", "content": f"Convert this analysis into structured format with cross_category_trends, emerging_themes, and attention_shifts:\n\n{analysis}"}],
                temperature=0.1
            )
            
            structured = response.choices[0].message.content
            
            # Parse the structured response
            import json
            try:
                return json.loads(structured)
            except:
                # Fallback to basic structure
                return {
                    "cross_category_trends": self._extract_section(structured, "Cross-Category Trends"),
                    "emerging_themes": self._extract_section(structured, "Emerging Themes"),
                    "attention_shifts": self._extract_section(structured, "Attention Shifts"),
                    "key_insights": self._extract_section(structured, "Key Insights")
                }
                
        except Exception as e:
            logger.error(f"Error parsing meta analysis: {str(e)}")
            return {}
            
    def _extract_section(self, text: str, section: str) -> List[str]:
        """Extract a section from structured text"""
        try:
            if section in text:
                section_text = text.split(section)[1].split("\n")
                return [line.strip("- ").strip() for line in section_text if line.strip()]
            return []
        except:
            return []
            
    def _parse_social_content(self, analysis: str) -> List[SocialContent]:
        """Parse social content from x.ai analysis"""
        try:
            # Use x.ai to structure the content
            response = self.xai_client.chat.completions.create(
                model=os.getenv("XAI_MODEL", "grok-1"),
                messages=[{"role": "user", "content": f"Convert this analysis into structured social media content items:\n\n{analysis}"}],
                temperature=0.1
            )
            
            structured = response.choices[0].message.content
            
            # Parse into SocialContent objects
            content = []
            for item in self._parse_content_items(structured):
                content.append(SocialContent(**item))
            return content
            
        except Exception as e:
            logger.error(f"Error parsing social content: {str(e)}")
            return []
            
    def _parse_tweet_analysis(self, analysis: str) -> List[SocialContent]:
        """Parse tweet analysis from x.ai output"""
        try:
            # Use x.ai to structure the analysis
            response = self.xai_client.chat.completions.create(
                model=os.getenv("XAI_MODEL", "grok-1"),
                messages=[{"role": "user", "content": f"Convert this analysis into structured tweet items:\n\n{analysis}"}],
                temperature=0.1
            )
            
            structured = response.choices[0].message.content
            
            # Parse into SocialContent objects
            content = []
            for item in self._parse_content_items(structured):
                content.append(SocialContent(**item))
            return content
            
        except Exception as e:
            logger.error(f"Error parsing tweet analysis: {str(e)}")
            return []
            
    def _parse_content_items(self, text: str) -> List[Dict[str, Any]]:
        """Parse content items from structured text"""
        try:
            import json
            try:
                return json.loads(text)
            except:
                # Fallback to basic parsing
                items = []
                current_item = {}
                
                for line in text.split("\n"):
                    if line.strip():
                        if ":" in line:
                            key, value = line.split(":", 1)
                            current_item[key.strip().lower()] = value.strip()
                        elif "---" in line:
                            if current_item:
                                items.append(current_item)
                                current_item = {}
                
                if current_item:
                    items.append(current_item)
                    
                return items
                
        except Exception as e:
            logger.error(f"Error parsing content items: {str(e)}")
            return []

    async def generate_summary(self, content_items: List[Union[Dict[str, Any], SocialContent]]) -> ResearchSummary:
        """Generate a summary from collected social content."""
        try:
            # Convert SocialContent objects to dictionaries if needed
            content_list = []
            for item in content_items:
                if isinstance(item, SocialContent):
                    content_list.append(item.dict())
                else:
                    content_list.append(item)
            
            # Prepare content for analysis
            content_text = "\n".join([item["content"] for item in content_list])
            
            completion = self.xai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research analyst specialized in summarizing social media discussions and identifying key trends."
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this social media content and provide a structured summary with key topics, insights, and sentiment:\n\n{content_text}"
                    }
                ],
                temperature=0.3,
                stream=False,
                max_tokens=2000
            )
            
            response = completion.choices[0].message.content
            
            # Extract topics and insights
            topics = []
            key_insights = []
            sentiment_scores = []
            
            for line in response.split("\n"):
                if line.startswith("Topic:"):
                    topics.append(line.replace("Topic:", "").strip())
                elif line.startswith("Insight:"):
                    key_insights.append(line.replace("Insight:", "").strip())
                
                # Calculate sentiment for each line
                sentiment_scores.append(self.sentiment_analyzer.polarity_scores(line)["compound"])
            
            # Calculate average sentiment
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
            
            # Get top influencers (placeholder for now)
            top_influencers = [
                {"name": "user1", "influence_score": 0.9},
                {"name": "user2", "influence_score": 0.8}
            ]
            
            return ResearchSummary(
                topics=topics,
                key_insights=key_insights,
                sentiment=avg_sentiment,
                sources=[item.get("platform", "unknown") for item in content_list],
                timestamp=datetime.now(),
                top_influencers=top_influencers
            )
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise

class CoinResearchAgent:
    """Agent for comprehensive coin research"""
    
    def __init__(self):
        self.llm_service = LLMIntentService()
        self.market_data = MarketDataService()
        self.model = os.getenv("XAI_MODEL", "grok-2-1212")
        self.xai_client = OpenAI(api_key=os.getenv("XAI_API_KEY"))
        self.perplexity_client = PerplexityClient()
        
    async def research_coin(self, token_symbol: str) -> CoinResearch:
        """Perform comprehensive research on a coin"""
        try:
            # Analyze whitepaper
            business_model = await self._analyze_whitepaper(token_symbol)
            print(f"Business model: {business_model}")
            # Research team
            team_analysis = await self._research_team(token_symbol)
            
            # Analyze tokenomics
            tokenomics = await self._analyze_tokenomics(token_symbol)
            
            # Scan social channels
            social_metrics = await self._scan_social_channels(token_symbol)
            
            # Identify risk factors
            risk_factors = await self._identify_risks(
                business_model,
                team_analysis,
                tokenomics,
                social_metrics
            )
            
            return CoinResearch(
                token_symbol=token_symbol,
                business_model=business_model,
                team_analysis=team_analysis,
                tokenomics=tokenomics,
                risk_factors=risk_factors,
                social_metrics=social_metrics,
                market_metrics=await self.market_data.get_token_metrics(token_symbol),
                sources=self._collect_sources(),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error researching coin {token_symbol}: {str(e)}")
            raise
            
    async def _analyze_whitepaper(self, token_symbol: str) -> Dict[str, Any]:
        """Analyze project whitepaper and documentation using real-time data"""
        try:
            # 1. Fetch real-time data
            real_time_data = await self._fetch_real_time_data(token_symbol)
            
            # 2. Use Perplexity API for initial research
            perplexity_query = f"""
            Research the {token_symbol} cryptocurrency token, focusing on:
            1. Its role as an AI agent
            2. Technical features and capabilities
            3. Recent developments and updates
            4. Market position and competitors
            
            Use only verified and recent information.
            """
            
            perplexity_response = await self.perplexity_client.analyze(perplexity_query)
            
            # 3. Combine and analyze data using x.ai
            combined_data = {
                "brave_search": real_time_data,
                "perplexity": perplexity_response
            }
            
            # 4. Use x.ai to synthesize information
            synthesis_prompt = f"""
            Analyze and synthesize the following real-time data about {token_symbol} token:
            
            Brave Search Results:
            {json.dumps(real_time_data, indent=2)}
            
            Perplexity Analysis:
            {perplexity_response}
            
            Provide a structured analysis focusing on:
            1. Core features and capabilities
            2. Technical architecture
            3. Market positioning
            4. Recent developments
            5. Key differentiators
            
            Only include verified information from the provided sources.
            """
            print(f"\n\nSynthesis prompt: {synthesis_prompt}\n\n")
            
            completion = self.xai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a crypto research analyst specializing in AI and blockchain projects. Analyze only verified information from provided sources."
                    },
                    {
                        "role": "user",
                        "content": synthesis_prompt
                    }
                ],
                temperature=0.3,
                stream=False,
                max_tokens=1500
            )
            
            analysis = completion.choices[0].message.content
            print(f"\n\nAnalysis: {analysis}\n\n")
            # 5. Structure the final analysis
            return {
                "overview": analysis,
                "sources": real_time_data["sources"],
                "last_updated": datetime.now().isoformat(),
                "raw_data": {
                    "brave_search": real_time_data,
                    "perplexity": perplexity_response
                }
            }
            
        except Exception as e:
            logger.error(f"Error in dynamic whitepaper analysis: {str(e)}", exc_info=True)
            raise
            
    async def _research_team(self, token_symbol: str) -> Dict[str, Any]:
        """Research project team"""
        try:
            # Collect team information
            team_info = await self._fetch_team_info(token_symbol)
            
            # Verify credentials
            verified_info = await self._verify_credentials(team_info)
            
            # Check track record
            track_record = await self._check_track_record(team_info)
            
            return {
                "core_team": verified_info,
                "track_record": track_record,
                "red_flags": await self._check_team_red_flags(verified_info)
            }
            
        except Exception as e:
            logger.error(f"Error researching team: {str(e)} ", exc_info=True)
            return {}
            
    async def _analyze_tokenomics(self, token_symbol: str) -> Dict[str, Any]:
        """Analyze project tokenomics"""
        try:
            # Fetch token data
            token_data = await self.market_data.get_token_data(token_symbol)
            
            return {
                "supply_metrics": await self._analyze_supply(token_data),
                "distribution": await self._analyze_distribution(token_data),
                "vesting": await self._analyze_vesting(token_data),
                "utility": await self._analyze_utility(token_data)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing tokenomics: {str(e)}")
            return {}
            
    async def _scan_social_channels(self, token_symbol: str) -> Dict[str, Any]:
        """Scan social media channels"""
        try:
            # Scan multiple platforms
            telegram = await self._scan_telegram(token_symbol)
            twitter = await self._scan_twitter(token_symbol)
            discord = await self._scan_discord(token_symbol)
            
            return {
                "community_metrics": self._analyze_community_metrics(telegram, twitter, discord),
                "sentiment_analysis": await self._analyze_social_sentiment(telegram, twitter, discord),
                "growth_metrics": self._calculate_growth_metrics(telegram, twitter, discord)
            }
            
        except Exception as e:
            logger.error(f"Error scanning social channels: {str(e)}")
            return {}
            
    async def _identify_risks(
        self,
        business_model: Dict[str, Any],
        team_analysis: Dict[str, Any],
        tokenomics: Dict[str, Any],
        social_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify potential risk factors"""
        risks = []
        
        # Business model risks
        risks.extend(self._analyze_business_risks(business_model))
        
        # Team risks
        risks.extend(self._analyze_team_risks(team_analysis))
        
        # Tokenomics risks
        risks.extend(self._analyze_tokenomics_risks(tokenomics))
        
        # Social/community risks
        risks.extend(self._analyze_social_risks(social_metrics))
        
        return risks 

    async def _fetch_real_time_data(self, token_symbol: str) -> Dict[str, Any]:
        """Fetch real-time data about the token from multiple sources"""
        try:
            # Brave Search API
            brave_api_url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": os.getenv("BRAVE_API_KEY")
            }
            
            # Search query for specific token info
            query = f"{token_symbol} token crypto AI agent blockchain"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    brave_api_url,
                    headers=headers,
                    params={
                        "q": query,
                        "count": 10,
                        "freshness": "pd"  # Past day for real-time info
                    }
                )
                
                brave_results = response.json()
                
                # Extract relevant information
                sources = []
                content = []
                
                for result in brave_results.get("web", {}).get("results", []):
                    sources.append(result["url"])
                    content.append({
                        "title": result["title"],
                        "description": result["description"],
                        "url": result["url"],
                        "published": result.get("published_time", "")
                    })
                    
                return {
                    "sources": sources,
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error fetching real-time data: {str(e)}")
            return {} 