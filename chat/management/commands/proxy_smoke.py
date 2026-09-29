from django.core.management.base import BaseCommand

from billing.models import AIModel
from billing.services import compute_cost, format_usd
from chat.providers import Delta, ProviderError, Usage, stream_chat


class Command(BaseCommand):
    help = "Send one short live message to each active model through the proxy. Costs real proxy quota."

    def add_arguments(self, parser):
        parser.add_argument("--prompt", default="Say hi in three words.")

    def handle(self, *args, **options):
        failures = 0
        for ai_model in AIModel.objects.filter(is_active=True):
            text, usage = [], None
            try:
                for event in stream_chat(ai_model, "Be brief.", [{"role": "user", "content": options["prompt"]}]):
                    if isinstance(event, Delta):
                        text.append(event.text)
                    elif isinstance(event, Usage):
                        usage = event
            except ProviderError as exc:
                failures += 1
                self.stdout.write(self.style.ERROR(f"{ai_model}: {exc}"))
                continue
            cost = compute_cost(ai_model, usage.input_tokens, usage.output_tokens)
            self.stdout.write(
                self.style.SUCCESS(f"{ai_model}: {''.join(text)!r}")
                + f"  in={usage.input_tokens} out={usage.output_tokens} price={format_usd(cost)}"
            )
        if failures:
            raise SystemExit(1)
