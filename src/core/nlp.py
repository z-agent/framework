"""
NLP Engine for DeFi interactions
Implements core NLP functionality using spaCy
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
import spacy
import logging

# Configure logging
logger = logging.getLogger(__name__)

class IntentType(str, Enum):
    """Types of supported intents"""
    TRADE = "trade"
    ANALYZE = "analyze"
    MONITOR = "monitor"
    STAKE = "stake"
    UNKNOWN = "unknown"

class Intent(BaseModel):
    """Intent classification result"""
    type: IntentType
    confidence: float
    params: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None

class TradeParams(BaseModel):
    """Parameters for trade intent"""
    token: str
    amount: float
    action: str = "buy"
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None

class NLPEngine:
    """Core NLP engine using spaCy"""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """Initialize NLP engine with spaCy model"""
        self.nlp = spacy.load(model_name)
        
        # Define intent patterns
        self.intent_patterns = {
            IntentType.TRADE: ["buy", "sell", "trade", "swap", "exchange"],
            IntentType.ANALYZE: ["analyze", "check", "review", "examine", "study"],
            IntentType.MONITOR: ["monitor", "track", "watch", "alert", "notify"],
            IntentType.STAKE: ["stake", "unstake", "delegate", "bond", "yield"]
        }
        
    def process_message(self, text: str) -> Intent:
        """Process a natural language message to determine intent"""
        # Create spaCy doc
        doc = self.nlp(text.lower())
        
        # Find best matching intent
        best_intent = IntentType.UNKNOWN
        best_confidence = 0.0
        
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if pattern in text.lower():
                    # Use spaCy's similarity to get confidence
                    pattern_doc = self.nlp(pattern)
                    confidence = max(doc.similarity(pattern_doc), 0.7)
                    
                    if confidence > best_confidence:
                        best_intent = intent_type
                        best_confidence = confidence
        
        # Parse parameters based on intent
        params = None
        if best_intent == IntentType.TRADE:
            params = self._parse_trade_params(doc)
        
        return Intent(
            type=best_intent,
            confidence=best_confidence,
            params=params
        )
    
    def _parse_trade_params(self, doc) -> Optional[Dict[str, Any]]:
        """Parse trade parameters from spaCy doc"""
        params = {}
        
        # Extract token and amount using spaCy's entity recognition
        for ent in doc.ents:
            if ent.label_ == "MONEY":
                try:
                    params["amount"] = float(ent.text.split()[0])
                except:
                    continue
            elif ent.label_ == "ORG":
                params["token"] = ent.text.upper()
        
        # Extract action
        for token in doc:
            if token.text in ["buy", "sell"]:
                params["action"] = token.text
                break
        
        return params if params else None
    
    def get_explanation(self, intent: Intent) -> str:
        """Generate natural language explanation of intent"""
        if intent.type == IntentType.TRADE:
            return self._get_trade_explanation(intent)
        elif intent.type == IntentType.ANALYZE:
            return "I'll analyze the market conditions and provide insights."
        elif intent.type == IntentType.MONITOR:
            return "I'll set up monitoring for the specified conditions."
        elif intent.type == IntentType.STAKE:
            return "I'll help you stake your assets safely and efficiently."
        else:
            return "I'm not sure what you want to do. Could you please rephrase?"
    
    def _get_trade_explanation(self, intent: Intent) -> str:
        """Generate explanation for trade intent"""
        if not intent.params:
            return "I understand you want to trade, but I need more details."
            
        action = intent.params.get("action", "trade")
        amount = intent.params.get("amount")
        token = intent.params.get("token")
        
        if amount and token:
            return f"I'll help you {action} {amount} {token} safely and efficiently."
        elif token:
            return f"I'll help you {action} {token} safely and efficiently."
        else:
            return f"I understand you want to {action}, but I need more details." 