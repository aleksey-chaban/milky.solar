"""Selectors"""

from app.config import (
    limiter,
    flask_api,
)

from app.src.integrations.openai import (
    get_story,
    unlock_story,
)

SCENARIOS = [
    "israel",
    "australia",
    "newzealand",
    "otherworld",
    "california",
    "unitedkingdom"
]

USER_SCENARIOS = [
    "guest",
    "israel",
    "australia",
    "newzealand",
    "otherworld",
    "california",
    "unitedkingdom",
    "random"
]

for scenario in SCENARIOS:
    lambda_function = lambda s=scenario: get_story(s)
    lambda_function = limiter.exempt(lambda_function)
    flask_api.add_url_rule(
        f"/{scenario}",
        f"get_{scenario}_story",
        lambda_function, methods=["GET"]
    )

OPTIONS = {
    scenario: {
        "prompt": f"Please tell me the story of {scenario.capitalize()}.",
        "database": scenario
    }
    for scenario in SCENARIOS
}

for scenario, details in OPTIONS.items():
    flask_api.add_url_rule(f"/new-{scenario}", f"unlock_{scenario}_story",
                           lambda s=details["prompt"], d=details["database"]: unlock_story(s, d),
                           methods=["GET"])
