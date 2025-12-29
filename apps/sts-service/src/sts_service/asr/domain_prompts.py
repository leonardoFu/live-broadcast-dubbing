"""
Domain-specific prompts for ASR vocabulary priming.

These prompts are passed to faster-whisper's initial_prompt parameter
to bias the model toward domain-specific vocabulary.
"""

# Domain prompts map
# Each prompt contains vocabulary and phrases typical of that domain
DOMAIN_PROMPTS: dict[str, str] = {
    "sports": (
        "Sports commentary: score, goal, touchdown, field goal, three-pointer, "
        "slam dunk, home run, strikeout, penalty, foul, timeout, halftime, "
        "overtime, championship, playoffs, finals, MVP, all-star, coach, referee."
    ),
    "football": (
        "NFL football: touchdown, field goal, extra point, two-point conversion, "
        "quarterback, running back, wide receiver, tight end, offensive line, "
        "defensive line, linebacker, cornerback, safety, interception, fumble, "
        "sack, blitz, red zone, end zone, first down, fourth down, punt, kickoff. "
        "Patrick Mahomes, Travis Kelce, Chiefs, Eagles, Cowboys, 49ers, Ravens."
    ),
    "basketball": (
        "NBA basketball: three-pointer, slam dunk, layup, free throw, rebound, "
        "assist, steal, block, turnover, fast break, pick and roll, alley-oop, "
        "court, paint, key, arc, baseline, backcourt. "
        "LeBron James, Stephen Curry, Kevin Durant, Lakers, Warriors, Celtics."
    ),
    "news": (
        "News broadcast: breaking news, developing story, sources confirm, "
        "according to officials, press conference, statement, investigation, "
        "legislation, policy, economy, inflation, markets, weather forecast."
    ),
    "interview": (
        "Interview conversation: Thank you for joining us. Tell us about. "
        "How would you describe. What's your perspective on. "
        "That's a great question. Absolutely. Definitely. I think. "
        "In my experience. Looking forward."
    ),
    "general": "",  # Empty prompt for no vocabulary priming
}


def get_domain_prompt(domain: str) -> str:
    """Get the vocabulary prompt for a specific domain.

    Args:
        domain: Domain name (sports, football, basketball, news, interview, general)

    Returns:
        Prompt string for the domain, or empty string for unknown domains
    """
    return DOMAIN_PROMPTS.get(domain.lower(), DOMAIN_PROMPTS["general"])
