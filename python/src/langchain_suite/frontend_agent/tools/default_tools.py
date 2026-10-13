"""Default extensible domain tools for the frontend agent showcase.

Provides initial implementations for:
1. `get_current_time`: Timezone-aware date and time lookup.
2. `get_random_quote`: Curated multi-category quotes for inspiration & wisdom.
"""

from __future__ import annotations

import random
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Dict, List
from langchain_core.tools import tool

# Curated repository of inspirational, technical, and philosophical quotes
QUOTE_REPOSITORY: Dict[str, List[Dict[str, str]]] = {
    "technology": [
        {
            "quote": "Any sufficiently advanced technology is indistinguishable from magic.",
            "author": "Arthur C. Clarke",
        },
        {
            "quote": "Simplicity is prerequisite for reliability.",
            "author": "Edsger W. Dijkstra",
        },
        {
            "quote": "The best way to predict the future is to invent it.",
            "author": "Alan Kay",
        },
        {
            "quote": "Software is eating the world, but AI is eating software.",
            "author": "Marc Andreessen (Adapted)",
        },
    ],
    "philosophy": [
        {
            "quote": "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
            "author": "Will Durant (on Aristotle)",
        },
        {
            "quote": "The unexamined life is not worth living.",
            "author": "Socrates",
        },
        {
            "quote": "He who has a why to live can bear almost any how.",
            "author": "Friedrich Nietzsche",
        },
    ],
    "motivation": [
        {
            "quote": "It always seems impossible until it's done.",
            "author": "Nelson Mandela",
        },
        {
            "quote": "Do what you can, with what you have, where you are.",
            "author": "Theodore Roosevelt",
        },
        {
            "quote": "Action is the foundational key to all success.",
            "author": "Pablo Picasso",
        },
    ],
    "science": [
        {
            "quote": "Somewhere, something incredible is waiting to be known.",
            "author": "Carl Sagan",
        },
        {
            "quote": "Science is a way of thinking much more than it is a body of knowledge.",
            "author": "Carl Sagan",
        },
    ],
}


@tool
def get_current_time(timezone: str = "UTC") -> str:
    """Return the current date, time, weekday, and UTC offset for a specified timezone.

    Args:
        timezone: Standard IANA timezone string, e.g. 'UTC', 'Europe/Berlin',
                  'America/New_York', 'Asia/Tokyo', or 'Europe/Athens'.
                  Defaults to 'UTC'.
    """
    clean_tz = timezone.strip()
    try:
        tz = ZoneInfo(clean_tz)
        now = datetime.now(tz)
    except ZoneInfoNotFoundError:
        # Fallback to UTC if timezone name unrecognized
        tz = ZoneInfo("UTC")
        now = datetime.now(tz)
        return (
            f"Note: Unrecognized timezone '{clean_tz}', defaulted to UTC. "
            f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} ({now.strftime('%A')})"
        )

    return (
        f"Current Time in {clean_tz}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} "
        f"({now.strftime('%A')}, ISO: {now.isoformat()})"
    )


@tool
def get_random_quote(category: str = "general") -> str:
    """Return an inspiring quote from a given thematic category.

    Args:
        category: The topic or category for the quote.
                  Supported: 'technology', 'philosophy', 'motivation', 'science', or 'general'/'all'.
    """
    cat = category.strip().lower()
    
    if cat in QUOTE_REPOSITORY and QUOTE_REPOSITORY[cat]:
        picked = random.choice(QUOTE_REPOSITORY[cat])
        return f"\"{picked['quote']}\" — {picked['author']} [{cat.title()}]"
    
    # If general or unknown category, choose from all available quotes
    all_quotes: List[tuple[str, Dict[str, str]]] = [
        (c, q) for c, quotes in QUOTE_REPOSITORY.items() for q in quotes
    ]
    picked_cat, picked = random.choice(all_quotes)
    return f"\"{picked['quote']}\" — {picked['author']} [{picked_cat.title()}]"

