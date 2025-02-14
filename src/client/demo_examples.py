"""
Solana Agent Swarm Demo Examples
This script contains example queries for testing the Solana Agent Swarm.
"""

DEMO_QUERIES = {
    "Network Status": [
        "Get current network TPS",
        "Check network performance and congestion",
        "What is the current Solana network status?"
    ],
    
    "Price Checks": [
        # USDC on Solana
        "Get price for token EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        # SOL/USD price feed
        "Check price of token 9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E",
        "What is the current price of USDC on Solana?"
    ],
    
    "Trading Operations": [
        # Trade 1 SOL for USDC
        "Trade 1.0 SOL to token EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v with 50 bps slippage",
        # Trade 10 USDC for SOL
        "Execute trade of 10 USDC to SOL with 1% slippage",
        "Buy 5 SOL using USDC with default slippage"
    ],
    
    "Address Lookups": [
        # Solana Foundation Stake Pool
        "Get information about address 5XdtyEDREHJXXW1CTtCsVjJFxsJtQkEqWwXXLysr2fYU",
        # Mango Markets v4
        "Look up details for address 78b8f4cGCwmZ9ysPFMWLaLTkkaYnUjwMJYStWe5RTSSX",
        "What is the name associated with Solana Foundation's stake pool?"
    ],
    
    "Staking Operations": [
        "Stake 10 SOL to validator",
        "Check staking rewards for my delegation",
        "What is the current staking APY?"
    ],
    
    "Complex Operations": [
        # Check price and execute trade if conditions met
        "Check USDC price and trade 1 SOL if price is above 100 USDC",
        # Monitor network and execute stake
        "Monitor network TPS and stake 5 SOL if TPS is above 3000",
        # Price monitoring and trading strategy
        "Track SOL price for 5 minutes and execute trade if it drops by 5%"
    ]
}

def print_demo_examples():
    print("\n=== Solana Agent Swarm Demo Examples ===\n")
    
    for category, queries in DEMO_QUERIES.items():
        print(f"\n{category}:")
        print("-" * len(category))
        for i, query in enumerate(queries, 1):
            print(f"{i}. {query}")
        print()

def get_random_example():
    import random
    categories = list(DEMO_QUERIES.keys())
    category = random.choice(categories)
    query = random.choice(DEMO_QUERIES[category])
    return f"Category: {category}\nQuery: {query}"

if __name__ == "__main__":
    print_demo_examples()
    print("\nRandom Example:")
    print(get_random_example()) 