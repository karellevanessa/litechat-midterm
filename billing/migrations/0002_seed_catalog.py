from django.db import migrations

# Provider cost before markup, in micro-dollars per 1M tokens. See doc/study/1790658061_litechat-core.md, 5.3.
MODELS = [
    {
        "provider": "openai",
        "model_id": "gpt-5.6-luna",
        "display_name": "GPT-5.6 Luna",
        "description": "OpenAI's fast, low-cost model for everyday questions and quick drafts.",
        "tier": "value",
        "input_price_micros": 250_000,
        "output_price_micros": 2_000_000,
        "sort_order": 10,
    },
    {
        "provider": "anthropic",
        "model_id": "claude-haiku-4-5-20251001",
        "display_name": "Claude Haiku 4.5",
        "description": "Anthropic's fast, low-cost model for responsive chat and routine work.",
        "tier": "value",
        "input_price_micros": 1_000_000,
        "output_price_micros": 5_000_000,
        "sort_order": 20,
    },
    {
        "provider": "google",
        "model_id": "gemini-3.8-flash",
        "display_name": "Gemini 3.8 Flash",
        "description": "Google's fast model for everyday questions, writing and coding.",
        "tier": "value",
        "input_price_micros": 300_000,
        "output_price_micros": 2_500_000,
        "sort_order": 30,
    },
]


def seed(apps, schema_editor):
    AIModel = apps.get_model("billing", "AIModel")
    PricingSettings = apps.get_model("billing", "PricingSettings")
    for data in MODELS:
        AIModel.objects.update_or_create(model_id=data["model_id"], defaults=data)
    PricingSettings.objects.get_or_create(pk=1, defaults={"markup_percent": 50, "signup_grant_micros": 2_000_000})


def unseed(apps, schema_editor):
    AIModel = apps.get_model("billing", "AIModel")
    AIModel.objects.filter(model_id__in=[m["model_id"] for m in MODELS]).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
