"""Supported gig platforms referenced in CrewAI prompts."""

SUPPORTED_PLATFORMS: tuple[str, ...] = (
    "Swiggy",
    "Zomato",
    "Blinkit",
    "Instamart",
    "BigBasket",
    "Jiomart",
    "Zepto",
    "Bistro",
)


def supported_platforms_hint() -> str:
    return ", ".join(SUPPORTED_PLATFORMS)
