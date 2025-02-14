import asyncio
import agentipy
import os
from crewai import Agent, Crew, Task
from crewai.tools import BaseTool
import inspect
import typing
from pydantic import Field, BaseModel, create_model
from solders.pubkey import Pubkey
import aiohttp
import contextlib
import base58
import re
import base64
from solders.transaction import VersionedTransaction

# Jupiter API endpoints
JUP_API = "https://quote-api.jup.ag/v6"

# Check whether the argument is marked as optional with the
# typing.Optional hint
def is_optional_arg(annotation):
    return isinstance(annotation, typing._GenericAlias) and (
        annotation.__origin__ is typing.Union
        and type(None) in annotation.__args__
    )

async def execute_jupiter_trade(input_mint: str, output_mint: str, amount: float, slippage_bps: int = 50):
    """Execute a trade using Jupiter API directly"""
    try:
        # Step 1: Get quote
        quote_url = (
            f"{JUP_API}/quote?"
            f"inputMint={input_mint}"
            f"&outputMint={output_mint}"
            f"&amount={int(amount * 1e9)}"  # Convert to lamports
            f"&slippageBps={slippage_bps}"
            f"&onlyDirectRoutes=true"
            f"&maxAccounts=20"
        )
        
        async with aiohttp.ClientSession() as session:
            # Get quote
            async with session.get(quote_url) as quote_response:
                if quote_response.status != 200:
                    raise Exception(f"Failed to fetch quote: {quote_response.status}")
                quote_data = await quote_response.json()
                
            # Execute swap
            swap_url = f"{JUP_API}/swap"
            swap_data = {
                "quoteResponse": quote_data,
                "userPublicKey": os.getenv("SOLANA_PUBLIC_KEY"),
                "wrapUnwrapSOL": True,
                "computeUnitPriceMicroLamports": 1,
                "asLegacyTransaction": True
            }
            
            async with session.post(swap_url, json=swap_data) as swap_response:
                if swap_response.status != 200:
                    raise Exception(f"Failed to prepare swap: {swap_response.status}")
                swap_result = await swap_response.json()
                
                # Return transaction data
                return {
                    "status": "success",
                    "input_amount": amount,
                    "output_amount": quote_data["outAmount"] / 1e9,
                    "price_impact": quote_data.get("priceImpactPct", 0),
                    "transaction": swap_result["swapTransaction"]
                }
                
    except Exception as e:
        raise Exception(f"Jupiter trade failed: {str(e)}")

async def run_async_method(method, **kwargs):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SolanaAgentSwarm/1.0",
        "Authorization": f"Bearer {os.getenv('SOLANA_API_KEY', '')}"
    }
    
    # Always remove session from kwargs as we'll manage it internally
    kwargs.pop('session', None)
    
    # Configure timeout and retry settings
    timeout = aiohttp.ClientTimeout(total=30)
    max_retries = 3
    retry_delay = 1
    
    # Special handling for trade method
    if method.__name__ == 'trade':
        try:
            # First check if token exists and has liquidity
            output_mint = kwargs.get('output_mint')
            input_mint = "So11111111111111111111111111111111111111112"  # SOL mint
            amount = kwargs.get('input_amount', 0.01)
            slippage = kwargs.get('slippage_bps', 50)
            
            network = "mainnet" if "mainnet" in os.getenv("SOLANA_RPC_URL", "").lower() else "devnet"
            print(f"\nExecuting Jupiter trade on {network}...")
            print(f"- Input: {amount} SOL")
            print(f"- Output token: {output_mint}")
            print(f"- Slippage: {slippage} bps")
            
            # Execute trade using Jupiter API
            result = await execute_jupiter_trade(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=slippage
            )
            print("✅ Trade prepared successfully")
            return result
            
        except Exception as e:
            print(f"Error in trade execution: {str(e)}")
            raise Exception(f"Trade failed: {str(e)}")
    
    # Default handling for other methods
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if 'headers' in inspect.signature(method).parameters:
                    kwargs['headers'] = headers
                try:
                    result = await method(**kwargs)
                    print(f"Method {method.__name__} executed successfully")
                    return result
                except Exception as e:
                    print(f"Error in method execution: {str(e)}")
                    raise
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                print(f"Failed after {max_retries} attempts: {str(e)}")
                raise Exception(f"Failed to execute after {max_retries} attempts: {str(e)}")
            print(f"Attempt {attempt + 1} failed, retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay * (attempt + 1))
        except Exception as e:
            print(f"Unexpected error in {method.__name__}: {str(e)}")
            raise Exception(f"Unexpected error: {str(e)}")


def is_valid_solana_address(address: str) -> bool:
    try:
        # Check length and format
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
            return False
        
        # Try to decode base58
        try:
            decoded = base58.b58decode(address)
            return len(decoded) == 32
        except:
            return False
            
        return True
    except:
        return False


def validate_token_inputs(method_name: str, kwargs: dict) -> tuple[bool, str]:
    if method_name in ['trade', 'fetch_price']:
        token_key = 'output_mint' if method_name == 'trade' else 'token_id'
        token = kwargs.get(token_key)
        
        if not token:
            return False, f"Missing {token_key}"
            
        if not is_valid_solana_address(token):
            return False, f"Invalid Solana address format for {token_key}: {token}"
            
        # Additional validations for trade
        if method_name == 'trade':
            input_amount = kwargs.get('input_amount')
            if not input_amount or input_amount <= 0:
                return False, "Input amount must be greater than 0"
            
            if input_amount > 0.1:
                return False, "Input amount exceeds maximum allowed (0.1 SOL)"
                
            slippage = kwargs.get('slippage_bps')
            if not slippage or not (0 <= slippage <= 10000):
                return False, "Slippage must be between 0 and 10000 bps"
            
            # Check if we're on devnet
            if "devnet" in os.getenv("SOLANA_RPC_URL", "").lower():
                # List of known working devnet tokens
                devnet_tokens = {
                    "So11111111111111111111111111111111111111112": "SOL",
                    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
                    "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU": "USDT"
                }
                
                if token not in devnet_tokens:
                    return False, f"Token not supported on devnet. Please use one of: {', '.join(devnet_tokens.values())}"
    
    elif method_name == 'get_address_name':
        address = kwargs.get('address')
        if not address:
            return False, "Missing address"
            
        if not is_valid_solana_address(address):
            return False, f"Invalid Solana address format: {address}"
            
    elif method_name == 'transfer':
        if not kwargs.get('to'):
            return False, "Missing destination address"
        if not is_valid_solana_address(kwargs['to']):
            return False, f"Invalid destination address format: {kwargs['to']}"
        if not kwargs.get('amount') or kwargs['amount'] <= 0:
            return False, "Amount must be greater than 0"
    
    return True, ""


def gen_tool(method_name, method):
    model_fields = {}
    arg_type_mapping = {}

    # Special handling for transfer method
    if method_name == 'transfer':
        model_fields = {
            'to': (str, Field(..., description="Destination address")),
            'amount': (float, Field(..., description="Amount to transfer", gt=0)),
        }
    else:
        for arg, arg_type in typing.get_type_hints(method).items():
            if arg_type == Pubkey:
                arg_type_mapping[arg] = Pubkey.from_string
                arg_type = str

            if not (arg_type in (bool, str, int, float, type(None))):
                if is_optional_arg(arg_type):
                    continue

                raise ValueError(
                    f"arg {arg} of {method_name} not of primitive type: {arg_type}"
                )

            model_fields[arg] = (
                arg_type,
                Field(..., description=arg.replace("_", " ").title()),
            )

    class Tool(BaseTool):
        name: str = method_name
        description: str = (
            inspect.getdoc(method) or f"Invoke {method_name} method."
        )
        args_schema: typing.Type[BaseModel] = create_model(
            method_name.replace("_", " ").title(), **model_fields
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def _run(self, **kwargs):
            try:
                print(f"\nExecuting {method_name} with args: {kwargs}")

                # Validate inputs
                is_valid, error_msg = validate_token_inputs(method_name, kwargs)
                if not is_valid:
                    raise ValueError(error_msg)

                # Convert types if needed
                for arg in kwargs:
                    if arg in arg_type_mapping:
                        kwargs[arg] = arg_type_mapping[arg](kwargs[arg])

                # Run the method
                with contextlib.closing(asyncio.new_event_loop()) as loop:
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(run_async_method(method, **kwargs))
                    print(f"{method_name} executed successfully")
                    return result

            except ValueError as e:
                print(f"Validation error in {method_name}: {str(e)}")
                raise
            except Exception as e:
                print(f"Error executing {method_name}: {str(e)}")
                raise Exception(f"Failed to execute {method_name}: {str(e)}")

    return Tool()


def gen_tools():
    # Validate environment variables
    rpc_url = os.getenv("SOLANA_RPC_URL")
    if not rpc_url:
        raise ValueError("SOLANA_RPC_URL environment variable is not set")
        
    private_key = os.getenv("SOLANA_PRIVATE_KEY")
    if not private_key:
        raise ValueError("SOLANA_PRIVATE_KEY environment variable is not set")
    
    print("\nInitializing SolanaAgentKit:")
    print(f"- RPC URL: {rpc_url}")
    print(f"- Private Key: {private_key[:8]}...")
    
    try:
        agent = agentipy.SolanaAgentKit(
            rpc_url=rpc_url,
            private_key=private_key
        )
        print("✅ Successfully initialized SolanaAgentKit")
    except Exception as e:
        print(f"❌ Error initializing SolanaAgentKit: {str(e)}")
        raise
    
    tools = []
    print("\nRegistering tools:")
    
    methods = inspect.getmembers(agent, predicate=inspect.iscoroutinefunction)
    registered_tools = 0
    
    for method_name, method in methods:
        if method_name.startswith("_"):
            continue
        if method_name not in {
            "trade",
            "fetch_price",
            "get_tps",
            "stake",
            "get_address_name",
            "transfer",
        }:
            continue

        try:
            print(f"- Adding {method_name} tool")
            tools.append(
                (
                    f"Solana {method_name.replace('_', ' ').title()}",
                    gen_tool(method_name, method),
                )
            )
            registered_tools += 1
            print(f"  ✅ Successfully registered {method_name} tool")
        except Exception as e:
            print(f"  ❌ Failed to register {method_name} tool: {str(e)}")

    print(f"\n✅ Successfully registered {registered_tools} tools")
    return tools
