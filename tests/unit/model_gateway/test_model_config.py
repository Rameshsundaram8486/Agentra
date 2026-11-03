from decimal import Decimal

import pytest

from app.composition import CONFIG_DIR
from app.model_gateway.errors import ModelConfigError
from app.model_gateway.providers.base import Attempt, ModelResponse, TokenUsage
from app.model_gateway.router import ModelConfig, load_model_config
from app.model_gateway.telemetry import cost_of, worst_case_cost

CONFIG = load_model_config(CONFIG_DIR / "models.yaml")


def test_business_analyst_runs_on_opus_5_5_at_high_effort_with_fallback() -> None:
    profile = CONFIG.profile("business_analyst")

    assert (profile.model, profile.effort, profile.refusal_fallback) == ("claude-opus-5-5", "high", True)
    assert CONFIG.profile("some_other_agent") == CONFIG.defaults
    assert CONFIG.defaults.effort == "medium"
    assert CONFIG.budget.monthly_usd == Decimal(50)


def test_cost_uses_each_attempts_own_model_and_cache_rates() -> None:
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000, cache_creation_input_tokens=200_000, cache_read_input_tokens=500_000)
    response = ModelResponse(text="", model="claude-opus-5-5", stop_reason="end_turn", attempts=(Attempt("claude-opus-5-5", usage),))

    cost = cost_of(CONFIG, response)

    # 1M x $4 + 0.1M x $20 + 0.2M x $5 + 0.5M x $0.20
    assert cost.usd == Decimal("7.100000") and cost.exact


def test_an_unpriced_fallback_model_is_costed_at_the_highest_rate_and_flagged() -> None:
    usage = TokenUsage(input_tokens=1_000, output_tokens=1_000)
    response = ModelResponse(
        text="", model="claude-opus-4-8", stop_reason="end_turn", fallback_used=True,
        attempts=(Attempt("claude-opus-5-5", TokenUsage(input_tokens=1_000)), Attempt("claude-opus-4-8", usage)),
    )

    cost = cost_of(CONFIG, response)

    assert cost.usd == Decimal("0.028000")  # (1000 x 4) + (1000 x 4 + 1000 x 20), per million
    assert not cost.exact


def test_worst_case_counts_every_output_token_and_doubles_for_a_possible_fallback() -> None:
    profile = CONFIG.profile("business_analyst")  # max_tokens 24000, fallback on

    reserve = worst_case_cost(CONFIG, profile, prompt_chars=30_000)

    one_attempt = (Decimal(10_001) * 4 + 24_000 * 20) / 1_000_000
    assert reserve == one_attempt * 2


def test_invalid_config_fails_loudly(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "models.yaml"
    raw = (CONFIG_DIR / "models.yaml").read_text(encoding="utf-8")

    path.write_text(raw.replace("effort: high", "effort: extreme"), encoding="utf-8")
    with pytest.raises(ModelConfigError, match="effort"):
        load_model_config(path)

    path.write_text(raw.replace("claude-opus-5-5: {input", "claude-other: {input"), encoding="utf-8")
    with pytest.raises(ModelConfigError, match="models without pricing"):
        load_model_config(path)


def test_overrides_must_produce_valid_profiles() -> None:
    data = CONFIG.model_dump()
    data["agents"] = {"x": {"max_tokens": 10}}
    with pytest.raises(ValueError, match="max_tokens"):
        ModelConfig.model_validate(data)
