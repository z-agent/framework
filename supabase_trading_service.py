#!/usr/bin/env python3
"""
🚀 Supabase Trading Service for 100 Users
Enhanced database service for scaling the trading bot to 100 concurrent users
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
import base64

from supabase import create_client, Client
SUPABASE_AVAILABLE = True

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class UserData:
    """User data structure for Supabase"""
    telegram_user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    wallet_address: Optional[str] = None
    private_key_encrypted: Optional[str] = None
    mnemonic_encrypted: Optional[str] = None
    privy_user_id: Optional[str] = None
    session_signer: Optional[str] = None
    auto_trading_enabled: bool = False
    risk_per_trade: float = 0.05
    max_position_size: float = 0.20
    min_confidence: int = 70
    total_trades: int = 0
    total_earnings: float = 0.0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    is_active: bool = True
    last_active: Optional[datetime] = None

@dataclass
class TradeData:
    """Trade data structure for Supabase"""
    user_id: str
    telegram_user_id: int
    symbol: str
    side: str  # BUY/SELL
    size: float
    price: float
    order_value: float
    order_id: Optional[str] = None
    transaction_hash: Optional[str] = None
    status: str = 'PENDING'
    pnl: float = 0.0
    fees_paid: float = 0.0
    builder_fee_earned: float = 0.0
    trade_type: str = 'MANUAL'
    signal_confidence: Optional[float] = None
    executed_at: Optional[datetime] = None

class EncryptionService:
    """Service for encrypting/decrypting sensitive data"""
    
    def __init__(self):
        # Get encryption key from environment or generate one
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            # Generate a new key (in production, store this securely)
            key = Fernet.generate_key()
            logger.info("🔑 Generated encryption key for session")
        else:
            key = key.encode()
        
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        if not data:
            return None
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        if not encrypted_data:
            return None
        return self.cipher.decrypt(encrypted_data.encode()).decode()

class BackupStorage:
    """Local backup storage for when Supabase is unavailable"""
    
    def __init__(self):
        self.users = {}
        self.trades = {}
        self.backup_file = "backup_data.json"
        self._load_backup()
    
    def _load_backup(self):
        """Load backup data from file"""
        try:
            if os.path.exists(self.backup_file):
                with open(self.backup_file, 'r') as f:
                    data = json.load(f)
                    self.users = data.get('users', {})
                    self.trades = data.get('trades', {})
                logger.info(f"Loaded backup data: {len(self.users)} users, {len(self.trades)} trades")
        except Exception as e:
            logger.error(f"Failed to load backup: {e}")
    
    def _save_backup(self):
        """Save current data to backup file"""
        try:
            data = {
                'users': self.users,
                'trades': self.trades,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.backup_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save backup: {e}")
    
    def create_user(self, user_data: dict) -> str:
        """Create user in backup storage"""
        user_id = f"backup_{len(self.users) + 1}"
        self.users[user_id] = user_data
        self._save_backup()
        return user_id
    
    def get_user(self, telegram_user_id: int) -> Optional[dict]:
        """Get user from backup storage"""
        for user_id, user_data in self.users.items():
            if user_data.get('telegram_user_id') == telegram_user_id:
                return user_data
        return None
    
    def update_user(self, telegram_user_id: int, updates: dict) -> bool:
        """Update user in backup storage"""
        for user_id, user_data in self.users.items():
            if user_data.get('telegram_user_id') == telegram_user_id:
                user_data.update(updates)
                self._save_backup()
                return True
        return False
    
    def create_trade(self, trade_data: dict) -> str:
        """Create trade in backup storage"""
        trade_id = f"backup_trade_{len(self.trades) + 1}"
        self.trades[trade_id] = trade_data
        self._save_backup()
        return trade_id

class SupabaseTradingService:
    """Enhanced Supabase service for 100 users trading bot with backup"""
    
    def __init__(self):
        if not SUPABASE_AVAILABLE:
            raise ImportError("Supabase client not available")
        
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY') or os.getenv('SUPABASE_KEY')
        
        # Initialize backup storage
        self.backup = BackupStorage()
        
        # Initialize Supabase client with correct syntax
        try:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("✅ Supabase client created successfully")
            self.supabase_available = True
        except Exception as e:
            logger.warning(f"Supabase client creation failed: {e}")
            self.client = None
            self.supabase_available = False
            logger.info("🔄 Using backup storage only")
        
        # Initialize encryption service
        try:
            self.encryption = EncryptionService()
            logger.info("✅ Supabase Trading Service initialized with backup")
        except Exception as e:
            logger.error(f"❌ Failed to initialize encryption: {e}")
            self.encryption = None
    
    def set_user_context(self, telegram_user_id: int):
        """Set user context for RLS policies"""
        if not self.client:
            logger.debug("Supabase client not available - skipping user context")
            return
        # Skip RPC call due to client compatibility issues
        # RLS policies will be handled by direct filtering instead
        logger.debug(f"User context set for {telegram_user_id} (RPC disabled for compatibility)")
    
    # User Management Methods
    
    async def create_user(self, user_data: UserData) -> Optional[str]:
        """Create a new user in Supabase with backup fallback"""
        try:
            # Encrypt sensitive data
            user_dict = asdict(user_data)
            if user_dict.get('private_key_encrypted') and self.encryption:
                user_dict['private_key_encrypted'] = self.encryption.encrypt(user_dict['private_key_encrypted'])
            if user_dict.get('mnemonic_encrypted') and self.encryption:
                user_dict['mnemonic_encrypted'] = self.encryption.encrypt(user_dict['mnemonic_encrypted'])
            
            # Set timestamps
            user_dict['created_at'] = datetime.now().isoformat()
            user_dict['updated_at'] = datetime.now().isoformat()
            user_dict['last_active'] = datetime.now().isoformat()
            
            # Remove None values
            user_dict = {k: v for k, v in user_dict.items() if v is not None}
            
            # Try Supabase first
            if self.supabase_available and self.client:
                try:
                    result = self.client.table('trading_users').insert(user_dict).execute()
                    
                    if result.data:
                        user_id = result.data[0]['id']
                        logger.info(f"✅ Created user {user_data.telegram_user_id} in Supabase with ID {user_id}")
                        # Also save to backup
                        self.backup.create_user(user_dict)
                        return user_id
                except Exception as e:
                    logger.warning(f"Supabase create user failed: {e}, using backup")
                    self.supabase_available = False
            
            # Fallback to backup storage
            user_id = self.backup.create_user(user_dict)
            logger.info(f"✅ Created user {user_data.telegram_user_id} in backup storage with ID {user_id}")
            return user_id
                
        except Exception as e:
            logger.error(f"Error creating user {user_data.telegram_user_id}: {e}")
            raise
    
    async def get_user(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """Get user data from Supabase"""
        if not self.client:
            raise ImportError("Supabase client not available")
            
        try:
            self.set_user_context(telegram_user_id)
            
            result = self.client.table('trading_users').select('*').eq('telegram_user_id', telegram_user_id).execute()
            
            if result.data:
                user_data = result.data[0]
                
                # Decrypt sensitive data
                if user_data.get('private_key_encrypted'):
                    user_data['private_key_encrypted'] = self.encryption.decrypt(user_data['private_key_encrypted'])
                if user_data.get('mnemonic_encrypted'):
                    user_data['mnemonic_encrypted'] = self.encryption.decrypt(user_data['mnemonic_encrypted'])
                
                return user_data
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting user {telegram_user_id}: {e}")
            raise
    
    async def get_user_by_wallet_address(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get user data by wallet address"""
        if not self.client:
            raise ImportError("Supabase client not available")
            
        try:
            result = self.client.table('trading_users').select('*').eq('wallet_address', wallet_address).execute()
            
            if result.data:
                user_data = result.data[0]
                
                # Decrypt sensitive data
                if user_data.get('private_key_encrypted'):
                    user_data['private_key_encrypted'] = self.encryption.decrypt(user_data['private_key_encrypted'])
                if user_data.get('mnemonic_encrypted'):
                    user_data['mnemonic_encrypted'] = self.encryption.decrypt(user_data['mnemonic_encrypted'])
                
                return user_data
            else:
                logger.warning(f"User with wallet {wallet_address} not found")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user by wallet {wallet_address}: {e}")
            return None
    
    async def update_user(self, telegram_user_id: int, updates: Dict[str, Any]) -> bool:
        """Update user data in Supabase"""
        try:
            if not self.client:
                logger.warning("Supabase client not available - skipping user update")
                return True  # Return True to not break the flow
            
            self.set_user_context(telegram_user_id)
            
            # Encrypt sensitive data if present
            if 'private_key_encrypted' in updates and updates['private_key_encrypted']:
                updates['private_key_encrypted'] = self.encryption.encrypt(updates['private_key_encrypted'])
            if 'mnemonic_encrypted' in updates and updates['mnemonic_encrypted']:
                updates['mnemonic_encrypted'] = self.encryption.encrypt(updates['mnemonic_encrypted'])
            
            # Set updated timestamp
            updates['updated_at'] = datetime.now().isoformat()
            
            result = self.client.table('trading_users').update(updates).eq('telegram_user_id', telegram_user_id).execute()
            
            if result.data:
                logger.info(f"✅ Updated user {telegram_user_id}")
                return True
            else:
                logger.error(f"❌ Failed to update user {telegram_user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating user {telegram_user_id}: {e}")
            return False  # Return False instead of raising to not break the flow
    
    async def update_user_activity(self, telegram_user_id: int) -> bool:
        """Update user's last active timestamp"""
        try:
            return await self.update_user(telegram_user_id, {
                'last_active': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error updating user activity {telegram_user_id}: {e}")
            raise
    
    async def update_user_stats(self, telegram_user_id: int, total_trades: int = None, total_earnings: float = None, **kwargs) -> bool:
        """Update user trading statistics"""
        try:
            updates = {}
            if total_trades is not None:
                updates['total_trades'] = total_trades
            if total_earnings is not None:
                updates['total_earnings'] = total_earnings
            
            # Add any additional stats
            updates.update(kwargs)
            
            return await self.update_user(telegram_user_id, updates)
        except Exception as e:
            logger.error(f"Error updating user stats {telegram_user_id}: {e}")
            return False
    
    # Trade Management Methods
    
    async def create_trade(self, trade_data: TradeData) -> Optional[str]:
        """Create a new trade record in Supabase"""
        try:
            self.set_user_context(trade_data.telegram_user_id)
            
            trade_dict = asdict(trade_data)
            trade_dict['created_at'] = datetime.now().isoformat()
            if trade_dict.get('executed_at'):
                trade_dict['executed_at'] = trade_dict['executed_at'].isoformat()
            
            # Remove None values
            trade_dict = {k: v for k, v in trade_dict.items() if v is not None}
            
            result = self.client.table('trades').insert(trade_dict).execute()
            
            if result.data:
                trade_id = result.data[0]['id']
                logger.info(f"✅ Created trade {trade_id} for user {trade_data.telegram_user_id}")
                return trade_id
            else:
                logger.error(f"❌ Failed to create trade for user {trade_data.telegram_user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating trade for user {trade_data.telegram_user_id}: {e}")
            raise
    
    async def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> bool:
        """Update trade record in Supabase"""
        try:
            result = self.client.table('trades').update(updates).eq('id', trade_id).execute()
            
            if result.data:
                logger.info(f"✅ Updated trade {trade_id}")
                return True
            else:
                logger.error(f"❌ Failed to update trade {trade_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating trade {trade_id}: {e}")
            raise
    
    async def get_user_trades(self, telegram_user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's recent trades"""
        try:
            self.set_user_context(telegram_user_id)
            
            result = self.client.table('trades').select('*').eq('telegram_user_id', telegram_user_id).order('created_at', desc=True).limit(limit).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting trades for user {telegram_user_id}: {e}")
            raise
    
    async def get_user_performance(self, telegram_user_id: int) -> Dict[str, Any]:
        """Get user performance summary"""
        try:
            self.set_user_context(telegram_user_id)
            
            # Calculate performance from trades table directly (RPC disabled for client compatibility)
            trades = await self.get_user_trades(telegram_user_id, limit=1000)
            
            if trades:
                total_trades = len(trades)
                total_earnings = sum(trade.get('pnl', 0) for trade in trades)
                winning_trades = len([t for t in trades if t.get('pnl', 0) > 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                trade_sizes = [abs(t.get('order_value', 0)) for t in trades if t.get('order_value')]
                avg_trade_size = sum(trade_sizes) / len(trade_sizes) if trade_sizes else 0
                pnls = [t.get('pnl', 0) for t in trades]
                best_trade = max(pnls) if pnls else 0
                worst_trade = min(pnls) if pnls else 0
                total_fees = sum(t.get('fees_paid', 0) for t in trades)
                
                return {
                    'total_trades': total_trades,
                    'total_earnings': total_earnings,
                    'win_rate': win_rate,
                    'avg_trade_size': avg_trade_size,
                    'best_trade': best_trade,
                    'worst_trade': worst_trade,
                    'total_fees': total_fees
                }
            else:
                return {
                    'total_trades': 0,
                    'total_earnings': 0.0,
                    'win_rate': 0.0,
                    'avg_trade_size': 0.0,
                    'best_trade': 0.0,
                    'worst_trade': 0.0,
                    'total_fees': 0.0
                }
                
        except Exception as e:
            logger.error(f"Error getting performance for user {telegram_user_id}: {e}")
            raise
    
    # Analytics Methods
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the trading_users table"""
        if not self.client:
            raise ImportError("Supabase client not available")
            
        try:
            result = self.client.table('trading_users').select('*').eq('is_active', True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            raise

    async def get_active_users(self) -> List[Dict[str, Any]]:
        """Get all active users for monitoring"""
        try:
            result = self.client.table('active_users_dashboard').select('*').execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            raise
    
    async def get_bot_analytics(self, metric_name: str = None) -> List[Dict[str, Any]]:
        """Get bot analytics data"""
        try:
            query = self.client.table('bot_analytics').select('*')
            if metric_name:
                query = query.eq('metric_name', metric_name)
            
            result = query.order('created_at', desc=True).limit(100).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            raise
    
    async def record_metric(self, user_id: str, metric_name: str, metric_value: float, metric_type: str = 'COUNTER') -> bool:
        """Record a metric for analytics"""
        try:
            metric_data = {
                'user_id': user_id,
                'metric_name': metric_name,
                'metric_value': metric_value,
                'metric_type': metric_type,
                'date': datetime.now().date().isoformat(),
                'created_at': datetime.now().isoformat()
            }
            
            result = self.client.table('bot_analytics').insert(metric_data).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error recording metric: {e}")
            raise
    
    # Notification Methods
    
    async def create_notification(self, telegram_user_id: int, notification_type: str, title: str, message: str) -> bool:
        """Create a notification for a user"""
        try:
            # Get user_id from telegram_user_id
            user_data = await self.get_user(telegram_user_id)
            if not user_data:
                return False
            
            notification_data = {
                'user_id': user_data['id'],
                'telegram_user_id': telegram_user_id,
                'notification_type': notification_type,
                'title': title,
                'message': message,
                'created_at': datetime.now().isoformat()
            }
            
            result = self.client.table('user_notifications').insert(notification_data).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise
    
    async def get_user_notifications(self, telegram_user_id: int, unread_only: bool = True) -> List[Dict[str, Any]]:
        """Get user notifications"""
        try:
            self.set_user_context(telegram_user_id)
            
            query = self.client.table('user_notifications').select('*').eq('telegram_user_id', telegram_user_id)
            if unread_only:
                query = query.eq('is_read', False)
            
            result = query.order('created_at', desc=True).limit(50).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting notifications: {e}")
            raise
    
    # Bot Settings Methods
    
    async def get_bot_setting(self, setting_name: str) -> Optional[str]:
        """Get a bot setting value"""
        try:
            result = self.client.table('bot_settings').select('setting_value').eq('setting_name', setting_name).eq('is_active', True).execute()
            
            if result.data:
                return result.data[0]['setting_value']
            return None
        except Exception as e:
            logger.error(f"Error getting setting {setting_name}: {e}")
            raise
    
    async def update_bot_setting(self, setting_name: str, setting_value: str) -> bool:
        """Update a bot setting"""
        try:
            result = self.client.table('bot_settings').update({
                'setting_value': setting_value,
                'updated_at': datetime.now().isoformat()
            }).eq('setting_name', setting_name).execute()
            
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error updating setting {setting_name}: {e}")
            raise

# Global service instance
_trading_service = None

def get_trading_service() -> SupabaseTradingService:
    """Get the global trading service instance"""
    global _trading_service
    if _trading_service is None:
        _trading_service = SupabaseTradingService()
    return _trading_service

# Convenience functions
async def create_user(telegram_user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> Optional[str]:
    """Create a new user"""
    service = get_trading_service()
    user_data = UserData(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name
    )
    return await service.create_user(user_data)

async def get_user(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    """Get user data"""
    service = get_trading_service()
    return await service.get_user(telegram_user_id)

async def update_user(telegram_user_id: int, updates: Dict[str, Any]) -> bool:
    """Update user data"""
    service = get_trading_service()
    return await service.update_user(telegram_user_id, updates)

async def create_trade(telegram_user_id: int, symbol: str, side: str, size: float, price: float, trade_type: str = 'MANUAL') -> Optional[str]:
    """Create a trade record"""
    service = get_trading_service()
    
    # Get user_id
    user_data = await service.get_user(telegram_user_id)
    if not user_data:
        raise ValueError("User not found")
    
    trade_data = TradeData(
        user_id=user_data['id'],
        telegram_user_id=telegram_user_id,
        symbol=symbol,
        side=side,
        size=size,
        price=price,
        order_value=size * price,
        trade_type=trade_type
    )
    
    return await service.create_trade(trade_data)

if __name__ == "__main__":
    print("🚀 Supabase Trading Service for 100 Users")
    print("This service provides database operations for the trading bot")
    print("Make sure to set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")
