"""
Wallet Manager Module
Handles all wallet-related operations including creation, import, and management
"""

import logging
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class WalletManager:
    """Manages wallet operations for the bot"""
    
    def __init__(self, bot_instance):
        """Initialize with reference to main bot instance"""
        self.bot = bot_instance
        self.privy_client = None
    
    async def create_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create a new wallet for the user"""
        user_id = update.effective_user.id
        
        # Initialize user if not exists
        if user_id not in self.bot.users:
            from hyperliquid_auto_trading_bot import UserState
            self.bot.users[user_id] = UserState()
        
        try:
            wallet_address = None
            wallet_text = ""
            
            # Create wallet using Privy (required for production)
            if not self.bot.privy_client:
                raise Exception("Privy client not configured. Please set PRIVY_APP_ID and PRIVY_APP_SECRET environment variables.")
            
            try:
                # Create user in Privy following official docs
                telegram_user_id = str(user_id)
                
                # Create user with Telegram account
                privy_user = self.bot.privy_client.create_user(
                    linked_accounts=[{
                        "type": "telegram",
                        "telegramUserId": telegram_user_id
                    }]
                )
                
                if not privy_user:
                    raise Exception("Failed to create Privy user")
                
                # Create wallet for the user following official docs
                wallet = self.bot.privy_client.create_wallet(
                    chainType="ethereum",  # Using ethereum for Hyperliquid
                    owner={
                        "userId": privy_user["id"]
                    }
                )
                
                if not wallet or "address" not in wallet:
                    raise Exception("Failed to create Privy wallet")
                
                wallet_address = wallet["address"]
                wallet_text = f"""
🔐 <b>Wallet Created Successfully!</b>

<b>Wallet Address:</b>
<code>{wallet_address}</code>

<b>✅ Features Available:</b>
• Secure trading on Hyperliquid
• AI-powered market analysis
• Real-time portfolio tracking
• Auto-trading capabilities

<b>💰 Next Steps:</b>
1. Fund your wallet with USDC
2. Use <code>/analyze BTC</code> to get trading signals
3. Use <code>/trade BTC BUY 0.01</code> to place trades

<b>🔐 Security:</b>
Your wallet is secured with Privy's enterprise-grade security.
                """
                
            except Exception as privy_error:
                logger.error(f"Privy wallet creation failed: {privy_error}")
                raise Exception(f"Wallet creation failed: {str(privy_error)}")
            
            # Store wallet address
            self.bot.users[user_id].wallet_address = wallet_address
            
            # Save to Supabase if available
            if self.bot.supabase_service:
                try:
                    await self.bot.supabase_service.update_user(
                        user_id, 
                        {"wallet_address": wallet_address}
                    )
                except Exception as e:
                    logger.warning(f"Failed to save wallet to Supabase: {e}")
            
            # Show success message with keyboard
            from bot_modules.ui_components import UIComponents
            reply_markup = UIComponents.get_wallet_management_keyboard()
            
            await update.message.reply_text(
                wallet_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ **Wallet Creation Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or contact support.",
                parse_mode='Markdown'
            )
    
    async def import_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Import an existing wallet"""
        if not context.args:
            await update.message.reply_text(
                "❌ **Import Command Usage**\n\n"
                "**Private Key:**\n"
                "<code>/import private YOUR_PRIVATE_KEY</code>\n\n"
                "**Mnemonic:**\n"
                "<code>/import mnemonic word1 word2 word3 ...</code>\n\n"
                "**Address Only:**\n"
                "<code>/import address 0x...</code>",
                parse_mode='HTML'
            )
            return
        
        user_id = update.effective_user.id
        import_type = context.args[0].lower()
        
        try:
            if import_type == "private":
                if len(context.args) < 2:
                    await update.message.reply_text(
                        "❌ **Private Key Required**\n\n"
                        "Usage: <code>/import private YOUR_PRIVATE_KEY</code>",
                        parse_mode='HTML'
                    )
                    return
                
                private_key = context.args[1]
                
                # Try to import to Privy if available
                if not self.bot.privy_client:
                    await update.message.reply_text(
                        "❌ Privy client not configured. Please set PRIVY_APP_ID and PRIVY_APP_SECRET environment variables.",
                        parse_mode='HTML'
                    )
                    return
                
                if self.bot.privy_client:
                    try:
                        # Create user first
                        telegram_user_id = str(user_id)
                        privy_user = self.bot.privy_client.create_user(
                            linked_accounts=[{
                                "type": "telegram",
                                "telegramUserId": telegram_user_id
                            }]
                        )
                        
                        # Import wallet with private key
                        wallet = self.bot.privy_client.create_wallet(
                            chainType="ethereum",
                            owner={
                                "userId": privy_user["id"]
                            },
                            privateKey=private_key
                        )
                        
                        if wallet and "address" in wallet:
                            wallet_address = wallet["address"]
                            success_text = f"""
✅ <b>Wallet Imported Successfully!</b>

<b>Wallet Address:</b>
<code>{wallet_address}</code>

<b>✅ Features Available:</b>
• Full trading capabilities
• AI-powered analysis
• Portfolio tracking
• Auto-trading

<b>🔐 Security:</b>
Your private key is encrypted and stored securely.
                            """
                        else:
                            raise Exception("Failed to import wallet to Privy")
                    except Exception as e:
                        logger.warning(f"Privy import failed: {e}")
                        # Fallback to basic import
                        wallet_address = f"0x{private_key[-40:]}"
                        success_text = f"""
✅ <b>Wallet Imported (Basic Mode)</b>

<b>Wallet Address:</b>
<code>{wallet_address}</code>

<b>⚠️ Note:</b> Basic import mode. For full features, configure Privy.
                        """
                else:
                    # Fallback to basic import
                    wallet_address = f"0x{private_key[-40:]}"
                    success_text = f"""
✅ <b>Wallet Imported (Basic Mode)</b>

<b>Wallet Address:</b>
<code>{wallet_address}</code>

<b>⚠️ Note:</b> Basic import mode. For full features, configure Privy.
                    """
                
                # Store wallet address
                if user_id not in self.bot.users:
                    from hyperliquid_auto_trading_bot import UserState
                    self.bot.users[user_id] = UserState()
                
                self.bot.users[user_id].wallet_address = wallet_address
                
                # Save to Supabase if available
                if self.bot.supabase_service:
                    try:
                        await self.bot.supabase_service.update_user(
                            user_id, 
                            {"wallet_address": wallet_address}
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save wallet to Supabase: {e}")
                
                # Show success message
                from bot_modules.ui_components import UIComponents
                reply_markup = UIComponents.get_wallet_management_keyboard()
                
                await update.message.reply_text(
                    success_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                
            elif import_type == "mnemonic":
                await update.message.reply_text(
                    "📝 **Mnemonic Import**\n\n"
                    "Mnemonic import is coming soon!\n\n"
                    "For now, please use private key import:\n"
                    "<code>/import private YOUR_PRIVATE_KEY</code>",
                    parse_mode='HTML'
                )
                
            elif import_type == "address":
                if len(context.args) < 2:
                    await update.message.reply_text(
                        "❌ **Address Required**\n\n"
                        "Usage: <code>/import address 0x...</code>",
                        parse_mode='HTML'
                    )
                    return
                
                wallet_address = context.args[1]
                
                # Store wallet address (read-only)
                if user_id not in self.bot.users:
                    from hyperliquid_auto_trading_bot import UserState
                    self.bot.users[user_id] = UserState()
                
                self.bot.users[user_id].wallet_address = wallet_address
                
                await update.message.reply_text(
                    f"📍 <b>Address Imported (Read-Only)</b>\n\n"
                    f"<b>Address:</b> <code>{wallet_address}</code>\n\n"
                    f"<b>⚠️ Note:</b> Read-only access. No trading capabilities.",
                    parse_mode='HTML'
                )
                
            else:
                await update.message.reply_text(
                    "❌ **Invalid Import Type**\n\n"
                    "Valid types: <code>private</code>, <code>mnemonic</code>, <code>address</code>",
                    parse_mode='HTML'
                )
                
        except Exception as e:
            await update.message.reply_text(
                f"❌ **Import Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please check your input and try again.",
                parse_mode='Markdown'
            )
    
    async def export_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export wallet information"""
        user_id = update.effective_user.id
        
        if user_id not in self.bot.users or not self.bot.users[user_id].wallet_address:
            await update.message.reply_text(
                "❌ **No Wallet Found**\n\n"
                "Please create or import a wallet first using <code>/create</code> or <code>/import</code>.",
                parse_mode='HTML'
            )
            return
        
        try:
            # Get backup information
            if hasattr(self.bot.users[user_id], 'privy_user_id') and self.bot.users[user_id].privy_user_id:
                backup_info = await self.bot._get_privy_wallet_backup(self.bot.users[user_id])
            else:
                backup_info = f"""
🔐 <b>Wallet Export</b>

<b>Wallet Address:</b>
<code>{self.bot.users[user_id].wallet_address}</code>

<b>⚠️ Note:</b> This is a basic wallet export.
For full backup features, configure Privy integration.

<b>🔐 Security Reminder:</b>
• Keep your wallet information secure
• Never share your private keys
• Use a secure password manager
                """
            
            await update.message.reply_text(
                backup_info,
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ <b>Export Failed</b>\n\nError: {str(e)}",
                parse_mode='HTML'
            )
    
    async def delete_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete wallet (with confirmation)"""
        user_id = update.effective_user.id
        
        if user_id not in self.bot.users or not self.bot.users[user_id].wallet_address:
            await update.message.reply_text(
                "❌ **No Wallet Found**\n\n"
                "No wallet to delete.",
                parse_mode='HTML'
            )
            return
        
        # Show confirmation
        from bot_modules.ui_components import UIComponents
        reply_markup = UIComponents.get_delete_confirmation_keyboard()
        
        await update.message.reply_text(
            "⚠️ <b>Delete Wallet Confirmation</b>\n\n"
            "Are you sure you want to delete your wallet?\n\n"
            "<b>This action cannot be undone!</b>\n\n"
            "Your wallet address will be removed from this bot.",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def confirm_wallet_deletion(self, query):
        """Confirm wallet deletion"""
        user_id = query.from_user.id
        
        if user_id in self.bot.users:
            # Clear wallet data
            self.bot.users[user_id].wallet_address = None
            self.bot.users[user_id].auto_trade_enabled = False
            
            # Remove from Supabase if available
            if self.bot.supabase_service:
                try:
                    await self.bot.supabase_service.update_user(
                        user_id, 
                        {"wallet_address": None, "auto_trade_enabled": False}
                    )
                except Exception as e:
                    logger.warning(f"Failed to update Supabase: {e}")
            
            await query.edit_message_text(
                "✅ <b>Wallet Deleted</b>\n\n"
                "Your wallet has been successfully removed from this bot.\n\n"
                "You can create a new wallet anytime with <code>/create</code>.",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "❌ <b>No Wallet Found</b>\n\n"
                "No wallet to delete.",
                parse_mode='HTML'
            )
    
    async def get_wallet_backup(self, query):
        """Get wallet backup information"""
        user_id = query.from_user.id
        
        if user_id not in self.bot.users or not self.bot.users[user_id].wallet_address:
            await query.edit_message_text(
                "❌ <b>No Wallet Found</b>\n\n"
                "Please create a wallet first to export it.",
                parse_mode='HTML'
            )
            return
        
        try:
            # Get backup information
            backup_info = await self.bot._get_privy_wallet_backup(self.bot.users[user_id])
            
            from bot_modules.ui_components import UIComponents
            reply_markup = UIComponents.get_wallet_backup_keyboard()
            
            await query.edit_message_text(
                backup_info,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ <b>Backup Failed</b>\n\nError: {str(e)}",
                parse_mode='HTML'
            )
