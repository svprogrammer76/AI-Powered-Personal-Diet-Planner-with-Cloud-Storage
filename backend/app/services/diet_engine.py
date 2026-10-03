import json
import os
from pathlib import Path

from app.config import settings

DATA_PATH = Path(__file__).resolve().parents[3] / "ai_engine" / "food_data.json"
NOTICE = "Educational general-wellness example only; not medical or clinical nutrition advice."


def rule_based_plan(profile: dict) -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    meals = data[profile["dietary_preference"]]
    goal_note = {
        "balanced": "A varied mix of familiar foods is shown as an example.",
        "weight_management": "Use regular, satisfying meals as a general example; no calorie target is prescribed.",
        "fitness": "The examples include varied foods around an active routine; portions are not prescribed.",
    }[profile["goal"]]
    avoid = {item.strip().lower() for item in profile.get("allergies", [])}
    for meal_name in meals:
        candidates = [choice for choice in meals[meal_name] if not any(term in choice.lower() for term in avoid)]
        meals[meal_name] = candidates[0] if candidates else f"Choose a suitable {meal_name} after checking ingredients for foods you avoid."
    return {
        **{meal: meals[meal] for meal in ("breakfast", "lunch", "snack", "dinner")},
        "nutrition_summary": f"Illustrative balanced-food pattern. {goal_note} Nutrition values are not clinically calculated.",
        "hydration_reminder": "Drink fluids regularly and adapt to your needs and local guidance.",
        "educational_notice": NOTICE,
        "source": "rule-based",
    }


async def generate_plan(profile: dict) -> dict:
    """Optional remote AI with bounded response shape and a safe local fallback."""
    if settings.openai_api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=12.0, max_retries=0)
            prompt_data = {k: profile[k] for k in ("age", "activity_level", "dietary_preference", "goal", "allergies")}
            response = await client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Return JSON only with breakfast, lunch, snack, dinner, nutrition_summary. Give general educational meal ideas, no diagnosis, treatment, calorie prescriptions, or medical claims. Honor dietary preference and avoid listed allergens. Keep each field under 400 characters."},
                    {"role": "user", "content": json.dumps(prompt_data)},
                ],
            )
            raw = json.loads(response.choices[0].message.content or "{}")
            required = ("breakfast", "lunch", "snack", "dinner", "nutrition_summary")
            if all(isinstance(raw.get(key), str) and 0 < len(raw[key]) <= 400 for key in required):
                return {**{key: raw[key] for key in required}, "hydration_reminder": "Drink fluids regularly and adapt to your needs and local guidance.", "educational_notice": NOTICE, "source": "ai-api"}
        except Exception:
            # Network/API/validation failures intentionally degrade to the deterministic local engine.
            pass
    return rule_based_plan(profile)
