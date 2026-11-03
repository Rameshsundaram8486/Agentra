"""Tokens, cache hits, cost and the model actually used per call, and the worst-case cost used for the cap."""

from dataclasses import dataclass
from decimal import ROUND_UP, Decimal

from app.model_gateway.providers.base import ModelResponse
from app.model_gateway.router import ModelConfig, ModelProfile

_MILLION = Decimal(1_000_000)
_MICRO_USD = Decimal("0.000001")
# Conservative: real text averages more characters per token than this, so the input estimate runs high.
_CHARS_PER_TOKEN = 3


@dataclass(frozen=True)
class CallCost:
    usd: Decimal
    exact: bool  # False when a model in the response had no listed price


def cost_of(config: ModelConfig, response: ModelResponse) -> CallCost:
    total, exact = Decimal(0), True
    for attempt in response.attempts:
        price, known = config.pricing(attempt.model)
        exact = exact and known
        usage = attempt.usage
        total += (
            usage.input_tokens * price.input
            + usage.output_tokens * price.output
            + usage.cache_creation_input_tokens * price.cache_write
            + usage.cache_read_input_tokens * price.cache_read
        ) / _MILLION
    return CallCost(total.quantize(_MICRO_USD, rounding=ROUND_UP), exact)


def worst_case_cost(config: ModelConfig, profile: ModelProfile, prompt_chars: int) -> Decimal:
    """Upper bound reserved against the cap before the call: uncached input and every output token used,
    twice when a refusal fallback could re-run the request on another model."""
    # The fallback model is chosen by the API, so its price is not known in advance.
    price = config.highest_pricing() if profile.refusal_fallback else config.pricing(profile.model)[0]
    one_attempt = (Decimal(prompt_chars // _CHARS_PER_TOKEN + 1) * price.input + profile.max_tokens * price.output) / _MILLION
    attempts = 2 if profile.refusal_fallback else 1
    return (one_attempt * attempts).quantize(_MICRO_USD, rounding=ROUND_UP)
