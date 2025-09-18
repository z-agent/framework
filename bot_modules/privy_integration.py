"""
Privy Integration Module
Handles wallet creation, management, and export with Privy
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PrivyUser:
    """Privy user data"""
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class PrivyWallet:
    """Privy wallet data"""
    address: str
    private_key: Optional[str] = None
    wallet_type: str = "EOA"
    created_at: Optional[str] = None

class PrivyIntegration:
    """Privy integration for wallet management"""
    
    def __init__(self, app_id: str, app_secret: str):
        """Initialize Privy integration"""
        self.app_id = app_id
        print(f"App ID: {app_id}")
        self.app_secret = app_secret
        print(f"App Secret: {app_secret}")
        self.base_url = "https://auth.privy.io/api/v1"
        import base64
        # Privy uses Basic Auth with app_secret as password
        auth_string = f"{app_id}:{app_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "privy-app-id": self.app_id
        }
    
    async def create_user(self, telegram_user_id: int, username: str = None) -> Optional[PrivyUser]:
        """Create a new Privy user"""
        try:
            async with httpx.AsyncClient() as client:
                # Create user with Telegram ID as external ID
                user_data = {
                    "externalId": f"telegram_{telegram_user_id}",
                    "email": f"user_{telegram_user_id}@telegram.privy",
                    "phone": None,
                    "customMetadata": {
                        "telegram_user_id": telegram_user_id,
                        "username": username,
                        "source": "telegram_bot"
                    }
                }
                print(f"User data: {user_data}")
                print(f"Headers: {self.headers}")
                
                response = await client.post(
                    f"{self.base_url}/users",
                    headers=self.headers,
                    json=user_data,
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    user_info = response.json()
                    return PrivyUser(
                        id=user_info["id"],
                        email=user_info.get("email"),
                        phone=user_info.get("phone"),
                        created_at=user_info.get("createdAt")
                    )
                else:
                    logger.error(f"Failed to create Privy user: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creating Privy user: {e}")
            return None
    
    async def get_user_by_telegram_id(self, telegram_user_id: int) -> Optional[PrivyUser]:
        """Get user by Telegram ID"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users",
                    headers=self.headers,
                    params={"externalId": f"telegram_{telegram_user_id}"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    users = response.json().get("data", [])
                    if users:
                        user_info = users[0]
                        return PrivyUser(
                            id=user_info["id"],
                            email=user_info.get("email"),
                            phone=user_info.get("phone"),
                            created_at=user_info.get("createdAt")
                        )
                return None
                
        except Exception as e:
            logger.error(f"Error getting Privy user: {e}")
            return None
    
    async def create_wallet(self, user_id: str, wallet_type: str = "EOA") -> Optional[PrivyWallet]:
        """Create a new wallet for user"""
        try:
            async with httpx.AsyncClient() as client:
                wallet_data = {
                    "userId": user_id,
                    "walletType": wallet_type
                }
                
                response = await client.post(
                    f"{self.base_url}/wallets",
                    headers=self.headers,
                    json=wallet_data,
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    wallet_info = response.json()
                    return PrivyWallet(
                        address=wallet_info["address"],
                        private_key=wallet_info.get("privateKey"),
                        wallet_type=wallet_info.get("walletType", "EOA"),
                        created_at=wallet_info.get("createdAt")
                    )
                else:
                    logger.error(f"Failed to create wallet: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            return None
    
    async def get_user_wallets(self, user_id: str) -> list[PrivyWallet]:
        """Get all wallets for a user"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/{user_id}/wallets",
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    wallets_data = response.json().get("data", [])
                    wallets = []
                    for wallet_info in wallets_data:
                        wallets.append(PrivyWallet(
                            address=wallet_info["address"],
                            private_key=wallet_info.get("privateKey"),
                            wallet_type=wallet_info.get("walletType", "EOA"),
                            created_at=wallet_info.get("createdAt")
                        ))
                    return wallets
                return []
                
        except Exception as e:
            logger.error(f"Error getting user wallets: {e}")
            return []
    
    async def export_wallet_private_key(self, user_id: str, wallet_address: str) -> Optional[str]:
        """Export wallet private key"""
        try:
            wallets = await self.get_user_wallets(user_id)
            for wallet in wallets:
                if wallet.address.lower() == wallet_address.lower():
                    return wallet.private_key
            return None
            
        except Exception as e:
            logger.error(f"Error exporting wallet: {e}")
            return None
    
    async def get_user_or_create(self, telegram_user_id: int, username: str = None) -> Tuple[PrivyUser, bool]:
        """Get existing user or create new one"""
        # Try to get existing user
        user = await self.get_user_by_telegram_id(telegram_user_id)
        print(f"User: {user}")
        if user:
            return user, False
        
        # Create new user
        user = await self.create_user(telegram_user_id, username)
        print(f"User: {user}")
        if user:
            return user, True
        
        return None, False
    
    async def get_or_create_wallet(self, user_id: str) -> Optional[PrivyWallet]:
        """Get existing wallet or create new one"""
        # Try to get existing wallets
        wallets = await self.get_user_wallets(user_id)
        if wallets:
            return wallets[0]  # Return first wallet
        
        # Create new wallet
        return await self.create_wallet(user_id)
    
    def get_export_instructions(self) -> str:
        """Get wallet export instructions"""
        return """
🔐 **Wallet Export Instructions**

Your smart wallet is Privy-backed, you can always export your private key anytime.

**How to export your wallet:**

1. **Via Privy Dashboard:**
   - Go to https://dashboard.privy.io
   - Sign in with your account
   - Navigate to Wallets section
   - Click "Export Private Key"
   - Copy and securely store your private key

2. **Via Bot Command:**
   - Use /export command in this bot
   - Your private key will be provided securely
   - Store it in a safe place

3. **Security Notes:**
   - Never share your private key with anyone
   - Store it in a secure password manager
   - Consider using hardware wallets for large amounts
   - This bot never stores your private key

**Need help?** Contact support or use /help for more commands.
        """
