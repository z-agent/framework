import json
import requests
import argparse
import sys
import os
import base64
import base58
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from dotenv import load_dotenv
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.rpc.commitment import Commitment
import time

load_dotenv()

JUP_API = "https://quote-api.jup.ag/v6"

def send_transaction(rpc_url: str, encoded_transaction: str, keypair: Keypair):
    """Send transaction using raw RPC endpoint"""
    headers = {
        "Content-Type": "application/json",
    }
    
    # Add API key if present
    if "?" in rpc_url:
        api_key = rpc_url.split("?")[1].split("=")[1]
        headers["Authorization"] = f"Bearer {api_key}"
        rpc_url = rpc_url.split("?")[0]
    
    try:
        # For now, just send the transaction without signing
        # This is temporary until we fix the signing issue
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded_transaction,
                {
                    "skipPreflight": True,
                    "maxRetries": 3,
                    "preflightCommitment": "confirmed"
                }
            ]
        }
        
        response = requests.post(rpc_url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to send transaction: {response.status_code}")
        
        result = response.json()
        if "error" in result:
            error_msg = result.get("error", {}).get("message", str(result["error"]))
            raise Exception(f"RPC error: {error_msg}")
            
        return result["result"]
        
    except Exception as e:
        raise Exception(f"Transaction failed: {str(e)}")

def get_token_decimals(token: str) -> int:
    """Get token decimals based on mint address"""
    KNOWN_TOKENS = {
        "So11111111111111111111111111111111111111112": 9,  # SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 6,  # USDC
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": 5,  # BONK
        "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU": 9,  # SAMO
        "jtojtomepa8beP8AuQc6eXt5FriJwfkmzuLzWWUdSbr": 6,  # JTO
    }
    return KNOWN_TOKENS.get(token, 9)  # Default to 9 decimals

def get_token_symbol(token: str) -> str:
    """Get token symbol based on mint address"""
    KNOWN_SYMBOLS = {
        "So11111111111111111111111111111111111111112": "SOL",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
        "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU": "SAMO",
        "jtojtomepa8beP8AuQc6eXt5FriJwfkmzuLzWWUdSbr": "JTO",
    }
    return KNOWN_SYMBOLS.get(token, token[:4] + "...")

def validate_wallet():
    """Validate wallet configuration and return keypair"""
    private_key = os.getenv("SOLANA_PRIVATE_KEY")
    if not private_key:
        raise Exception("SOLANA_PRIVATE_KEY not set in environment")
        
    try:
        keypair = Keypair.from_base58_string(private_key)
        print(f"\nUsing wallet: {str(keypair.pubkey())}")
        return keypair
    except Exception as e:
        raise Exception(f"Invalid private key: {str(e)}")

def build_and_send_transaction(rpc_url: str, base64_tx: str, keypair: Keypair):
    """Build and send transaction from base64 encoded transaction"""
    headers = {
        "Content-Type": "application/json",
    }
    
    # Add API key if present
    if "?" in rpc_url:
        api_key = rpc_url.split("?")[1].split("=")[1]
        headers["Authorization"] = f"Bearer {api_key}"
        rpc_url = rpc_url.split("?")[0]
    
    try:
        # Decode base64 transaction
        decoded_tx = base64.b64decode(base64_tx)
        
        # Create versioned transaction from bytes
        transaction = VersionedTransaction.from_bytes(decoded_tx)
        
        # Get message bytes for signing
        message_bytes = bytes(transaction.message)
        
        # Sign message and create signature
        signature = keypair.sign_message(message_bytes)
        
        # Set the signature in the transaction
        transaction.signatures = [signature]
        
        # Get recent blockhash
        blockhash_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getLatestBlockhash",
            "params": [{"commitment": "confirmed"}]
        }
        
        response = requests.post(rpc_url, headers=headers, json=blockhash_payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get blockhash: {response.status_code}")
            
        result = response.json()
        if "error" in result:
            raise Exception(f"Failed to get blockhash: {result['error']}")
            
        blockhash = result["result"]["value"]["blockhash"]
        last_valid_block_height = result["result"]["value"]["lastValidBlockHeight"]
        
        # Serialize the signed transaction
        serialized_tx = base64.b64encode(bytes(transaction)).decode('utf-8')
        
        # Send transaction
        send_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                serialized_tx,
                {
                    "encoding": "base64",
                    "skipPreflight": True,
                    "maxRetries": 3,
                    "preflightCommitment": "confirmed",
                    "minContextSlot": last_valid_block_height
                }
            ]
        }
        
        print("\nSending transaction to network...")
        response = requests.post(rpc_url, headers=headers, json=send_payload)
        if response.status_code != 200:
            raise Exception(f"Failed to send transaction: {response.status_code}")
        
        result = response.json()
        if "error" in result:
            error_msg = result.get("error", {}).get("message", str(result["error"]))
            raise Exception(f"RPC error: {error_msg}")
            
        signature_str = result["result"]
        print(f"Transaction sent! Signature: {signature_str}")
        return signature_str
        
    except Exception as e:
        print(f"\nError details: {str(e)}")
        raise Exception(f"Transaction failed: {str(e)}")

def check_transaction_status(rpc_url: str, signature: str, max_retries: int = 5):
    """Check the status of a transaction with retries"""
    headers = {
        "Content-Type": "application/json",
    }
    
    # Add API key if present
    if "?" in rpc_url:
        api_key = rpc_url.split("?")[1].split("=")[1]
        headers["Authorization"] = f"Bearer {api_key}"
        rpc_url = rpc_url.split("?")[0]
    
    for attempt in range(max_retries):
        try:
            # Get transaction status
            status_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {
                        "encoding": "json",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0
                    }
                ]
            }
            
            response = requests.post(rpc_url, headers=headers, json=status_payload)
            if response.status_code != 200:
                raise Exception(f"Failed to get transaction status: {response.status_code}")
            
            result = response.json()
            if "error" in result:
                error_msg = result.get("error", {}).get("message", str(result["error"]))
                if "not found" in error_msg.lower() and attempt < max_retries - 1:
                    print(f"\rWaiting for confirmation... ({attempt + 1}/{max_retries})", end="")
                    time.sleep(1)  # Wait 1 second before retrying
                    continue
                raise Exception(f"RPC error: {error_msg}")
                
            tx_data = result.get("result")
            if not tx_data:
                if attempt < max_retries - 1:
                    print(f"\rWaiting for confirmation... ({attempt + 1}/{max_retries})", end="")
                    time.sleep(1)  # Wait 1 second before retrying
                    continue
                raise Exception("Transaction not found")
                
            # Check transaction status
            if tx_data.get("meta", {}).get("err") is not None:
                raise Exception(f"Transaction failed: {tx_data['meta']['err']}")
                
            print("\n\nTransaction Status:")
            print(f"✅ Confirmed")
            print(f"Block: {tx_data.get('slot', 'unknown')}")
            print(f"Fee: {tx_data.get('meta', {}).get('fee', 0) / 1e9:.9f} SOL")
            
            # Check for successful token transfers
            post_balances = tx_data.get("meta", {}).get("postTokenBalances", [])
            pre_balances = tx_data.get("meta", {}).get("preTokenBalances", [])
            
            if post_balances and pre_balances:
                for post in post_balances:
                    # Find matching pre-balance
                    pre = next((x for x in pre_balances if x["mint"] == post["mint"]), None)
                    if pre:
                        pre_amount = float(pre.get("uiTokenAmount", {}).get("uiAmount", 0))
                        post_amount = float(post.get("uiTokenAmount", {}).get("uiAmount", 0))
                        symbol = get_token_symbol(post["mint"])
                        change = post_amount - pre_amount
                        if change != 0:
                            print(f"Token Change ({symbol}): {change:+,.6f}")
            
            return True
            
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"\n\n❌ Error checking transaction: {str(e)}")
                return False
            continue

def get_balance(rpc_url: str, wallet: str, token: str = None):
    """Get SOL and token balances for a wallet"""
    headers = {
        "Content-Type": "application/json",
    }
    
    # Add API key if present
    if "?" in rpc_url:
        api_key = rpc_url.split("?")[1].split("=")[1]
        headers["Authorization"] = f"Bearer {api_key}"
        rpc_url = rpc_url.split("?")[0]
    
    try:
        # Get SOL balance
        sol_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet]
        }
        
        response = requests.post(rpc_url, headers=headers, json=sol_payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get balance: {response.status_code}")
            
        result = response.json()
        if "error" in result:
            raise Exception(f"RPC error: {result['error']}")
            
        sol_balance = result["result"]["value"] / 1e9
        print(f"\nSOL Balance: {sol_balance:.9f}")
        
        # Get token balance if specified
        if token:
            token_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet,
                    {
                        "mint": token
                    },
                    {
                        "encoding": "jsonParsed"
                    }
                ]
            }
            
            response = requests.post(rpc_url, headers=headers, json=token_payload)
            if response.status_code != 200:
                raise Exception(f"Failed to get token balance: {response.status_code}")
                
            result = response.json()
            if "error" in result:
                raise Exception(f"RPC error: {result['error']}")
                
            accounts = result["result"]["value"]
            if accounts:
                decimals = get_token_decimals(token)
                balance = int(accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) / (10 ** decimals)
                symbol = get_token_symbol(token)
                print(f"{symbol} Balance: {balance:,.6f}")
            else:
                print(f"No token account found for {get_token_symbol(token)}")
                
        return True
            
    except Exception as e:
        print(f"Error getting balance: {str(e)}")
        return False

def execute_trade(token: str, qty: float, slippage: int):
    """Execute a trade using Jupiter API directly"""
    try:
        # Get RPC URL and validate
        rpc_url = os.getenv("SOLANA_RPC_URL")
        if not rpc_url:
            raise Exception("SOLANA_RPC_URL not set in environment")
            
        # Network info
        network = "Devnet" if "devnet" in rpc_url.lower() else "Mainnet"
        print(f"\nNetwork: {network}")
        
        # Validate wallet
        keypair = validate_wallet()
        
        # Check balances before trade
        print("\nChecking balances before trade...")
        get_balance(rpc_url, str(keypair.pubkey()), token)
        
        # Step 1: Get quote
        input_mint = "So11111111111111111111111111111111111111112"  # SOL mint
        quote_url = (
            f"{JUP_API}/quote?"
            f"inputMint={input_mint}"
            f"&outputMint={token}"
            f"&amount={int(qty * 1e9)}"  # Convert to lamports
            f"&slippageBps={slippage}"
            f"&onlyDirectRoutes=true"
        )
        
        # Get quote
        quote_response = requests.get(quote_url)
        if quote_response.status_code != 200:
            raise Exception(f"Failed to fetch quote: {quote_response.status_code}")
        quote_data = quote_response.json()
        
        # Get token info
        output_decimals = get_token_decimals(token)
        output_symbol = get_token_symbol(token)
        output_amount = int(quote_data['outAmount']) / (10 ** output_decimals)
        
        print("\nTrade Quote:")
        print(f"Input: {qty} SOL")
        print(f"Output: {output_amount:,.6f} {output_symbol}")
        print(f"Price Impact: {quote_data.get('priceImpactPct', 0)}%")
        
        # Get swap transaction
        swap_url = f"{JUP_API}/swap"
        swap_data = {
            "quoteResponse": quote_data,
            "userPublicKey": str(keypair.pubkey()),
            "wrapUnwrapSOL": True,
            "computeUnitPriceMicroLamports": 1,  # Default value
            "asLegacyTransaction": True,  # Use legacy transactions for better compatibility
        }
        
        print("\nPreparing swap transaction...")
        swap_response = requests.post(swap_url, json=swap_data)
        if swap_response.status_code != 200:
            error_text = swap_response.text
            try:
                error_json = swap_response.json()
                error_text = json.dumps(error_json, indent=2)
            except:
                pass
            print(f"\nJupiter API Error Response:\n{error_text}")
            raise Exception(f"Failed to prepare swap: {swap_response.status_code}")
            
        swap_result = swap_response.json()
        if 'error' in swap_result:
            raise Exception(f"Jupiter API error: {swap_result['error']}")
            
        if 'swapTransaction' not in swap_result:
            raise Exception("No swap transaction returned from Jupiter")
            
        # Send the signed transaction
        print("\nSending transaction...")
        signature = build_and_send_transaction(rpc_url, swap_result['swapTransaction'], keypair)
        
        # Validate signature format
        if not signature or len(signature) != 88:  # Solana signatures are 88 characters
            raise Exception("Invalid transaction signature returned")
            
        print(f"\n✅ Trade executed successfully!")
        print(f"Transaction signature: {signature}")
        
        # Add explorer URL based on network
        if "devnet" in rpc_url.lower():
            print(f"View on Explorer: https://explorer.solana.com/tx/{signature}?cluster=devnet")
        else:
            print(f"View on Explorer: https://explorer.solana.com/tx/{signature}")
            
        # Check transaction status with increased retries
        print("\nVerifying transaction...")
        for i in range(5):  # Try 5 times
            time.sleep(1)  # Wait between checks
            if check_transaction_status(rpc_url, signature, max_retries=1):
                return True, {
                    "signature": signature,
                    "input_amount": qty,
                    "input_symbol": "SOL",
                    "output_amount": output_amount,
                    "output_symbol": output_symbol,
                    "price_impact": quote_data.get('priceImpactPct', 0)
                }
            print(f"Attempt {i+1}/5: Waiting for confirmation...")
            
        print("\n⚠️ Note: Transaction sent but confirmation is taking longer than expected.")
        print(f"Please check the transaction status on Solana Explorer:")
        print(f"https://explorer.solana.com/tx/{signature}")
        return True, {
            "signature": signature,
            "status": "pending",
            "message": "Transaction sent but awaiting confirmation"
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"\nError executing trade: {error_msg}")
        return False, error_msg

def main():
    parser = argparse.ArgumentParser(description='Solana Blockchain Client')
    parser.add_argument('--action', choices=['trade', 'balance'], required=True, help='Action to perform')
    parser.add_argument('--token', help='Token address for trade/balance action')
    parser.add_argument('--qty', type=float, help='Quantity for trade action')
    parser.add_argument('--slippage', type=int, default=50, help='Slippage in bps for trade action')
    
    args = parser.parse_args()

    if args.action == 'balance':
        rpc_url = os.getenv("SOLANA_RPC_URL")
        if not rpc_url:
            print("Error: SOLANA_RPC_URL not set in environment")
            sys.exit(1)
        keypair = validate_wallet()
        success = get_balance(rpc_url, str(keypair.pubkey()), args.token)
        sys.exit(0 if success else 1)
    elif args.action == 'trade':
        if not args.token or not args.qty:
            print("Error: --token and --qty are required for trade action")
            sys.exit(1)
        
        success, result = execute_trade(args.token, args.qty, args.slippage)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 