from src.core.registry import tool


@tool
def simulate_search(query: str) -> str:
    """
    Simulates a web search for a given query. Use this if the user asks for current events.
    """
    # In a real bot, you would use requests to call Google Custom Search or Tavily API
    return f"Results for '{query}': 1. Documentation on Discord Bots. 2. Python Architecture patterns."


@tool
def roll_dice(sides: int = 6) -> str:
    """
    Rolls a virtual die. Default sides is 6.
    """
    import random

    result = random.randint(1, sides)
    return f"Rolled a d{sides} and got: {result}"
