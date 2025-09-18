#!/usr/bin/env python3
"""
🔥 REDDIT BUSINESS INTELLIGENCE TOOL
Extract top posts from any subreddit to identify market opportunities
Perfect for "Reddit to SaaS in 15 minutes" viral demos
"""

import requests
import json
import time
from typing import Dict, Any, List
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
import re
from urllib.parse import quote

class RedditAnalysisSchema(BaseModel):
    """Schema for Reddit subreddit analysis"""
    subreddit: str = Field(default="gaming", description="Subreddit name (without r/ prefix, e.g., 'gaming', 'PCGaming', 'PS5'). Defaults to 'gaming' if not specified.")
    time_filter: str = Field(default="month", description="Time filter: hour, day, week, month, year, all")
    limit: int = Field(default=10, description="Number of posts to fetch (1-25)")
    sort_by: str = Field(default="top", description="Sort by: hot, new, top, rising")

class RedditBusinessIntelTool(BaseTool):
    """Extract business opportunities from Reddit posts"""
    name: str = "Reddit Business Intelligence"
    description: str = "Analyze Reddit posts to identify market pain points and business opportunities"
    args_schema: type = RedditAnalysisSchema

    def _run(self, **kwargs) -> Dict[str, Any]:
        # Aggressively reject empty or invalid inputs
        if not kwargs or kwargs == {}:
            error_msg = "❌ REJECTED: Reddit tool called with empty parameters. This causes infinite loops. Use proper parameters like {'subreddit': 'startups', 'time_filter': 'month', 'limit': 5, 'sort_by': 'top'}"
            print(error_msg)
            return {
                "error": error_msg,
                "posts": [],
                "total_engagement": 0,
                "success": False,
                "loop_detected": True,
                "required_format": {
                    "subreddit": "startups",
                    "time_filter": "month", 
                    "limit": 5,
                    "sort_by": "top"
                }
            }
        
        # Validate required parameters
        required_params = ["subreddit"]
        missing_params = [param for param in required_params if not kwargs.get(param)]
        if missing_params:
            error_msg = f"❌ REJECTED: Missing required parameters: {missing_params}. Use: {{'subreddit': 'startups', 'time_filter': 'month', 'limit': 5, 'sort_by': 'top'}}"
            print(error_msg)
            return {
                "error": error_msg,
                "posts": [],
                "total_engagement": 0,
                "success": False,
                "missing_parameters": missing_params
            }
        
        # Handle empty or invalid inputs gracefully
        subreddit = kwargs.get("subreddit", "gaming").strip()
        time_filter = kwargs.get("time_filter", "month")
        limit = min(kwargs.get("limit", 10), 25)  # Cap at 25 for API limits
        sort_by = kwargs.get("sort_by", "top")
        
        # Ensure subreddit is not empty
        if not subreddit:
            subreddit = "gaming"
            print(f"⚠️  Empty subreddit, using default: r/{subreddit}")
        
        # Validate and sanitize inputs
        valid_time_filters = ["hour", "day", "week", "month", "year", "all"]
        valid_sort_by = ["hot", "new", "top", "rising"]
        
        if time_filter not in valid_time_filters:
            time_filter = "month"
            print(f"⚠️  Invalid time_filter '{time_filter}', using default: month")
        
        if sort_by not in valid_sort_by:
            sort_by = "top"
            print(f"⚠️  Invalid sort_by '{sort_by}', using default: top")
        
        if not isinstance(limit, int) or limit < 1 or limit > 25:
            limit = 10
            print(f"⚠️  Invalid limit '{limit}', using default: 10")
        
        # Add a safety check to prevent infinite loops
        if hasattr(self, '_call_count'):
            self._call_count += 1
        else:
            self._call_count = 1
            
        if self._call_count > 3:
            error_msg = "Reddit tool called too many times - possible infinite loop detected"
            print(f"❌ {error_msg}")
            return {"error": error_msg, "posts": [], "total_engagement": 0, "success": False, "loop_detected": True}
        
        try:
            # Clean subreddit name
            subreddit = subreddit.replace("r/", "").strip()
            
            # Use Reddit JSON API (no auth required)
            url = f"https://www.reddit.com/r/{subreddit}/{sort_by}.json"
            
            params = {
                "limit": limit,
                "t": time_filter  # time filter for top posts
            }
            
            headers = {
                "User-Agent": "ZaraFramework:BusinessIntel:v1.0.0 (by u/ZaraAI)"
            }
            
            print(f"🔍 Fetching top {limit} posts from r/{subreddit}...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if "data" not in data or "children" not in data["data"]:
                return {"error": f"Invalid response from r/{subreddit}", "posts": [], "total_engagement": 0, "success": False}
            
            posts = []
            total_engagement = 0
            
            for post_data in data["data"]["children"]:
                post = post_data["data"]
                
                # Skip pinned/stickied posts
                if post.get("stickied", False):
                    continue
                
                # Extract key information
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                score = post.get("score", 0)
                num_comments = post.get("num_comments", 0)
                upvote_ratio = post.get("upvote_ratio", 0)
                created_utc = post.get("created_utc", 0)
                permalink = post.get("permalink", "")
                
                # Calculate engagement score
                engagement = score + (num_comments * 2)
                total_engagement += engagement
                
                # Clean and truncate text
                content = selftext[:500] + "..." if len(selftext) > 500 else selftext
                
                # Add post to list
                posts.append({
                    "title": title,
                    "content": content,
                    "score": score,
                    "comments": num_comments,
                    "engagement": engagement,
                    "upvote_ratio": upvote_ratio,
                    "permalink": f"https://reddit.com{permalink}",
                    "created": created_utc
                })
            
            # Sort by engagement
            posts.sort(key=lambda x: x["engagement"], reverse=True)
            
            # Return structured data
            return {
                "subreddit": subreddit,
                "time_filter": time_filter,
                "sort_by": sort_by,
                "posts_found": len(posts),
                "posts": posts[:limit],  # Ensure we don't exceed requested limit
                "total_engagement": total_engagement,
                "average_engagement": total_engagement / len(posts) if posts else 0,
                "success": True,
                "call_count": self._call_count
            }
            
        except requests.exceptions.Timeout:
            error_msg = f"Timeout fetching data from r/{subreddit}"
            print(f"❌ {error_msg}")
            return {"error": error_msg, "posts": [], "total_engagement": 0, "success": False}
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch data from r/{subreddit}: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg, "posts": [], "total_engagement": 0, "success": False}
            
        except Exception as e:
            error_msg = f"Unexpected error analyzing r/{subreddit}: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg, "posts": [], "total_engagement": 0, "success": False}
    
    def _extract_pain_points(self, posts: List[Dict]) -> List[str]:
        """Extract common pain points from post titles and content"""
        pain_indicators = [
            "help", "problem", "issue", "struggle", "difficult", "hard", "can't", "unable",
            "frustrated", "stuck", "confused", "lost", "don't know", "need advice",
            "what should i do", "how do i", "is there a way", "looking for",
            "recommendations", "suggestions", "alternatives", "better way"
        ]
        
        pain_points = []
        for post in posts:
            text = (post["title"] + " " + post["content"]).lower()
            
            # Look for pain indicators
            for indicator in pain_indicators:
                if indicator in text and post["engagement_score"] > 50:
                    # Extract the sentence containing the pain point
                    sentences = text.split(".")
                    for sentence in sentences:
                        if indicator in sentence and len(sentence.strip()) > 10:
                            pain_points.append(sentence.strip()[:200])
                            break
        
        # Remove duplicates and return top pain points
        unique_pains = list(set(pain_points))
        return unique_pains[:10]
    
    def _identify_themes(self, posts: List[Dict]) -> List[str]:
        """Identify common themes and topics"""
        themes = {}
        common_words = [
            "budget", "money", "debt", "credit", "loan", "mortgage", "investment",
            "savings", "retirement", "tax", "insurance", "bank", "financial",
            "income", "expense", "emergency fund", "401k", "ira", "stocks",
            "crypto", "real estate", "car", "student loan", "credit card"
        ]
        
        for post in posts:
            text = (post["title"] + " " + post["content"]).lower()
            for word in common_words:
                if word in text:
                    themes[word] = themes.get(word, 0) + post["engagement_score"]
        
        # Sort themes by total engagement
        sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)
        return [theme[0] for theme in sorted_themes[:8]]
    
    def _calculate_opportunity_score(self, posts: List[Dict]) -> str:
        """Calculate business opportunity score based on engagement and pain points"""
        if not posts:
            return "Low"
        
        avg_engagement = sum(p["engagement_score"] for p in posts) / len(posts)
        high_engagement_posts = len([p for p in posts if p["engagement_score"] > avg_engagement])
        
        if avg_engagement > 200 and high_engagement_posts > 5:
            return "Very High"
        elif avg_engagement > 100 and high_engagement_posts > 3:
            return "High"
        elif avg_engagement > 50:
            return "Medium"
        else:
            return "Low"

# Export for registration
reddit_business_intel_tool = RedditBusinessIntelTool() 