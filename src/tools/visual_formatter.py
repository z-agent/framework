#!/usr/bin/env python3
"""
Visual Formatter for Trading Analysis
Creates beautiful visual cards using advanced Unicode and optional HTML screenshots
"""

import io
import base64
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.patches import FancyBboxPatch
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

@dataclass
class TradingSignal:
    type: str  # BUY, SELL, WAIT
    confidence: int  # 0-100
    entry: float
    stop_loss: float
    take_profit: float
    reasoning: str

class VisualFormatter:
    """Creates beautiful visual trading analysis"""
    
    def __init__(self):
        # Advanced Unicode characters for better visuals
        self.chars = {
            'top_left': '╭',
            'top_right': '╮', 
            'bottom_left': '╰',
            'bottom_right': '╯',
            'horizontal': '─',
            'vertical': '│',
            'cross': '┼',
            'block_full': '█',
            'block_three_quarters': '▊',
            'block_half': '▌', 
            'block_quarter': '▎',
            'block_empty': '░',
            'arrow_up': '↗',
            'arrow_down': '↘',
            'circle_filled': '●',
            'circle_empty': '○',
            'diamond': '◆',
            'star': '★'
        }
    
    def create_analysis_card(self, symbol: str, price: float, signal: TradingSignal, data_source: str = "Real-time") -> str:
        """Create a beautiful analysis card using advanced Unicode"""
        
        # Signal styling
        if signal.type == "BUY":
            signal_emoji = "🟢"
            signal_color = "📈"
            direction = self.chars['arrow_up']
        elif signal.type == "SELL":
            signal_emoji = "🔴" 
            signal_color = "📉"
            direction = self.chars['arrow_down']
        else:
            signal_emoji = "⚪"
            signal_color = "➡️"
            direction = "─"
        
        # Confidence bar
        filled_blocks = int(signal.confidence / 10)
        confidence_bar = (self.chars['block_full'] * filled_blocks + 
                         self.chars['block_empty'] * (10 - filled_blocks))
        
        # Calculate R:R ratio
        if signal.type == "BUY":
            risk = abs(signal.entry - signal.stop_loss)
            reward = abs(signal.take_profit - signal.entry)
        else:
            risk = abs(signal.stop_loss - signal.entry)
            reward = abs(signal.entry - signal.take_profit)
        
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Potential percentages
        if signal.type == "BUY":
            potential_gain = ((signal.take_profit - signal.entry) / signal.entry * 100) if signal.entry > 0 else 0
            potential_loss = ((signal.entry - signal.stop_loss) / signal.entry * 100) if signal.entry > 0 else 0
        else:
            potential_gain = ((signal.entry - signal.take_profit) / signal.entry * 100) if signal.entry > 0 else 0
            potential_loss = ((signal.stop_loss - signal.entry) / signal.entry * 100) if signal.entry > 0 else 0
        
        # Create the visual card
        card = f"""
{self.chars['top_left']}{self.chars['horizontal'] * 42}{self.chars['top_right']}
{self.chars['vertical']} {signal_color} **{symbol} ANALYSIS** {' ' * (28 - len(symbol))} {self.chars['vertical']}
{self.chars['vertical']}{' ' * 42}{self.chars['vertical']}
{self.chars['vertical']} 💰 **Price**: ${price:,.2f}{' ' * (29 - len(f"${price:,.2f}"))} {self.chars['vertical']}
{self.chars['vertical']} 📡 **Source**: {data_source}{' ' * (27 - len(data_source))} {self.chars['vertical']}
{self.chars['vertical']}{' ' * 42}{self.chars['vertical']}
{self.chars['bottom_left']}{self.chars['horizontal'] * 42}{self.chars['bottom_right']}

{signal_emoji} **TRADING SIGNAL**: {signal.type} {direction}

{self.chars['top_left']}{self.chars['horizontal'] * 42}{self.chars['top_right']}
{self.chars['vertical']} 🎯 **Confidence**: {signal.confidence}%{' ' * (25 - len(str(signal.confidence)))} {self.chars['vertical']}
{self.chars['vertical']} {confidence_bar} {' ' * (15 - len(confidence_bar))} {self.chars['vertical']}
{self.chars['vertical']}{' ' * 42}{self.chars['vertical']}
{self.chars['vertical']} 🎪 **Entry**: ${signal.entry:,.4f}{' ' * (25 - len(f"${signal.entry:,.4f}"))} {self.chars['vertical']}
{self.chars['vertical']} 🛑 **Stop Loss**: ${signal.stop_loss:,.4f}{' ' * (19 - len(f"${signal.stop_loss:,.4f}"))} {self.chars['vertical']}
{self.chars['vertical']} 🎯 **Take Profit**: ${signal.take_profit:,.4f}{' ' * (17 - len(f"${signal.take_profit:,.4f}"))} {self.chars['vertical']}
{self.chars['vertical']}{' ' * 42}{self.chars['vertical']}
{self.chars['vertical']} ⚖️ **Risk:Reward**: 1:{rr_ratio:.1f}{' ' * (22 - len(f"1:{rr_ratio:.1f}"))} {self.chars['vertical']}
{self.chars['vertical']} 📈 **Potential Gain**: +{potential_gain:.1f}%{' ' * (17 - len(f"+{potential_gain:.1f}%"))} {self.chars['vertical']}
{self.chars['vertical']} 📉 **Potential Loss**: -{potential_loss:.1f}%{' ' * (17 - len(f"-{potential_loss:.1f}%"))} {self.chars['vertical']}
{self.chars['bottom_left']}{self.chars['horizontal'] * 42}{self.chars['bottom_right']}

🧠 **AI ANALYSIS**
{signal.reasoning}

🔗 **VERIFY DATA**
• [CoinGecko](https://www.coingecko.com/en/coins/{symbol.lower()}) | [CMC](https://coinmarketcap.com/currencies/{symbol.lower()}/)
"""
        return card
    
    def create_analysis_image(self, symbol: str, price: float, signal: TradingSignal, user_name: str = "Trader", width: int = 500, height: int = 700) -> Optional[bytes]:
        """Create a beautiful analysis image using matplotlib"""
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        # Set up dark theme
        plt.style.use('dark_background')
        
        fig, ax = plt.subplots(figsize=(width/100, height/100), facecolor='#1a1a1a')
        ax.set_facecolor('#1a1a1a')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 14)
        ax.axis('off')
        
        # Colors
        colors = {
            'BUY': '#00d4aa',
            'SELL': '#ff6b6b', 
            'WAIT': '#ffd43b',
            'text': '#ffffff',
            'text_muted': '#b0b0b0',
            'card_bg': '#2d2d2d',
            'border': '#404040'
        }
        
        signal_color = colors.get(signal.type, colors['WAIT'])
        
        # Main card background
        card_bg = FancyBboxPatch((0.5, 1), 9, 12, 
                                boxstyle="round,pad=0.1",
                                facecolor=colors['card_bg'],
                                edgecolor=colors['border'],
                                linewidth=2)
        ax.add_patch(card_bg)
        
        # Header
        ax.text(5, 12, f'📊 {symbol} ANALYSIS', 
                ha='center', va='center', fontsize=18, weight='bold',
                color=colors['text'])
        
        # Price
        ax.text(5, 11, f'💰 Current Price: ${price:,.2f}', 
                ha='center', va='center', fontsize=14, 
                color=colors['text'])
        
        # Signal
        signal_emoji = '🟢' if signal.type == 'BUY' else '🔴' if signal.type == 'SELL' else '⚪'
        ax.text(5, 10, f'{signal_emoji} TRADING SIGNAL: {signal.type}', 
                ha='center', va='center', fontsize=16, weight='bold',
                color=signal_color)
        
        # Confidence bar
        confidence_width = signal.confidence / 100 * 6
        confidence_bg = patches.Rectangle((2, 8.8), 6, 0.4, 
                                        facecolor='#404040', alpha=0.5)
        ax.add_patch(confidence_bg)
        confidence_fill = patches.Rectangle((2, 8.8), confidence_width, 0.4, 
                                          facecolor=signal_color)
        ax.add_patch(confidence_fill)
        ax.text(5, 9, f'🎯 Confidence: {signal.confidence}%', 
                ha='center', va='center', fontsize=12, color=colors['text'])
        
        # Trading levels
        y_pos = 7.5
        levels = [
            f'🎪 Entry Price: ${signal.entry:,.4f}',
            f'🛑 Stop Loss: ${signal.stop_loss:,.4f}',
            f'🎯 Take Profit: ${signal.take_profit:,.4f}'
        ]
        
        for level in levels:
            ax.text(5, y_pos, level, ha='center', va='center', 
                   fontsize=12, color=colors['text'])
            y_pos -= 0.7
        
        # Risk/Reward
        if signal.type == "BUY":
            risk = abs(signal.entry - signal.stop_loss)
            reward = abs(signal.take_profit - signal.entry)
        else:
            risk = abs(signal.stop_loss - signal.entry)
            reward = abs(signal.entry - signal.take_profit)
        
        rr_ratio = reward / risk if risk > 0 else 0
        ax.text(5, 4.5, f'⚖️ Risk:Reward = 1:{rr_ratio:.1f}', 
                ha='center', va='center', fontsize=12, color=colors['text'])
        
        # Potential gains/losses
        if signal.type == "BUY":
            potential_gain = ((signal.take_profit - signal.entry) / signal.entry * 100) if signal.entry > 0 else 0
            potential_loss = ((signal.entry - signal.stop_loss) / signal.entry * 100) if signal.entry > 0 else 0
        else:
            potential_gain = ((signal.entry - signal.take_profit) / signal.entry * 100) if signal.entry > 0 else 0
            potential_loss = ((signal.stop_loss - signal.entry) / signal.entry * 100) if signal.entry > 0 else 0
        
        ax.text(5, 3.8, f'📈 Potential Gain: +{potential_gain:.1f}%', 
                ha='center', va='center', fontsize=12, color=colors['BUY'])
        ax.text(5, 3.1, f'📉 Potential Loss: -{potential_loss:.1f}%', 
                ha='center', va='center', fontsize=12, color=colors['SELL'])
        
        # Analysis text (truncated)
        analysis_text = signal.reasoning[:100] + "..." if len(signal.reasoning) > 100 else signal.reasoning
        ax.text(5, 2, f'🧠 {analysis_text}', 
                ha='center', va='center', fontsize=10, 
                color=colors['text_muted'], wrap=True)
        
        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor='#1a1a1a', 
                   bbox_inches='tight', dpi=100, pad_inches=0.2)
        buf.seek(0)
        image_bytes = buf.getvalue()
        plt.close()
        
        return image_bytes

    def create_position_card_image(self, portfolio_data: Dict[str, Any]) -> Optional[bytes]:
        """Create beautiful portfolio image"""
        if not MATPLOTLIB_AVAILABLE:
            return None
            
        # Implementation for portfolio cards
        # This would create the dark theme portfolio visualization
        pass

# Global formatter instance
_visual_formatter = None

def get_visual_formatter() -> VisualFormatter:
    """Get global visual formatter instance"""
    global _visual_formatter
    if _visual_formatter is None:
        _visual_formatter = VisualFormatter()
    return _visual_formatter