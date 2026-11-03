"""The Claude provider against a stand-in SDK client: what is sent, and how real SDK response types are read."""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types.beta import BetaMessage

from app.model_gateway.errors import ModelProviderError
from app.model_gateway.providers.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.model_gateway.providers.base import ModelRequest

REQUEST = ModelRequest(
    model="claude-opus-5-5",
    effort="high",
    max_tokens=24_000,
    system="You are the Business Analyst Agent.",
    user="<project_brief>...</project_brief>",
    output_schema={"type": "object", "properties": {}, "additionalProperties": False},
    refusal_fallback=True,
    timeout_seconds=240,
    max_retries=2,
)


def _message(**overrides: Any) -> BetaMessage:
    data: dict[str, Any] = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": '{"ok": true}'}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 1200, "output_tokens": 800, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 400},
    }
    data.update(overrides)
    return BetaMessage.model_validate(data)


class _Stream:
    request_id = "req_test_123"

    def __init__(self, message: BetaMessage) -> None:
        self._message = message

    def __enter__(self) -> "_Stream":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_final_message(self) -> BetaMessage:
        return self._message


class _Client:
    def __init__(self, result: BetaMessage | Exception) -> None:
        self.result = result
        self.params: list[dict[str, Any]] = []
        self.options: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def with_options(self, **options: Any) -> "_Client":
        self.options.append(options)
        return self

    def _stream(self, **params: Any) -> _Stream:
        self.params.append(params)
        if isinstance(self.result, Exception):
            raise self.result
        return _Stream(self.result)


def test_request_sends_effort_schema_fallback_and_a_cached_system_prompt() -> None:
    client = _Client(_message())

    AnthropicProvider(None, client=client).complete(REQUEST)

    params = client.params[0]
    assert params["model"] == "claude-opus-5-5"
    assert params["output_config"] == {"effort": "high", "format": {"type": "json_schema", "schema": REQUEST.output_schema}}
    assert params["betas"] == [FALLBACK_BETA] and params["fallbacks"] == "default"
    assert params["system"] == [{"type": "text", "text": REQUEST.system, "cache_control": {"type": "ephemeral"}}]
    assert params["messages"] == [{"role": "user", "content": REQUEST.user}]
    # Opus 5.5 always thinks and rejects sampling parameters: none of these may be sent.
    assert not {"thinking", "temperature", "top_p", "top_k"} & set(params)
    assert client.options == [{"timeout": 240, "max_retries": 2}]


def test_without_fallback_no_beta_is_requested() -> None:
    client = _Client(_message())
    request = ModelRequest(**{**REQUEST.__dict__, "refusal_fallback": False})

    AnthropicProvider(None, client=client).complete(request)

    assert "betas" not in client.params[0] and "fallbacks" not in client.params[0]


def test_plain_response_is_read_from_top_level_usage() -> None:
    response = AnthropicProvider(None, client=_Client(_message())).complete(REQUEST)

    assert (response.text, response.model, response.stop_reason, response.fallback_used) == ('{"ok": true}', "claude-opus-5-5", "end_turn", False)
    assert response.usage.input_tokens == 1200 and response.usage.cache_read_input_tokens == 400
    assert response.request_id == "req_test_123"


def test_fallback_is_detected_from_usage_iterations_and_each_attempt_is_kept() -> None:
    message = _message(
        model="claude-opus-4-8",
        usage={
            "input_tokens": 1000,
            "output_tokens": 900,
            "iterations": [
                {"type": "message", "model": "claude-opus-5-5", "input_tokens": 1000, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
                {"type": "fallback_message", "model": "claude-opus-4-8", "input_tokens": 1000, "output_tokens": 900, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
            ],
        },
    )

    response = AnthropicProvider(None, client=_Client(message)).complete(REQUEST)

    assert response.fallback_used and response.model == "claude-opus-4-8"
    assert [attempt.model for attempt in response.attempts] == ["claude-opus-5-5", "claude-opus-4-8"]
    assert response.usage.input_tokens == 2000


def test_refusal_category_is_recorded() -> None:
    message = _message(content=[], stop_reason="refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": None})

    response = AnthropicProvider(None, client=_Client(message)).complete(REQUEST)

    assert (response.stop_reason, response.refusal_category, response.text) == ("refusal", "cyber", "")


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("failed", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (_status_error(anthropic.RateLimitError, 429), "rate_limited", True),
        (_status_error(anthropic.InternalServerError, 500), "provider_unavailable", True),
        (_status_error(anthropic.AuthenticationError, 401), "provider_auth", False),
        (_status_error(anthropic.BadRequestError, 400), "bad_request", False),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "provider_unreachable", True),
    ],
)
def test_sdk_errors_become_normalised_gateway_errors(error: Exception, code: str, retryable: bool) -> None:
    with pytest.raises(ModelProviderError) as caught:
        AnthropicProvider(None, client=_Client(error)).complete(REQUEST)

    assert (caught.value.code, caught.value.retryable) == (code, retryable)


def test_missing_api_key_is_a_clear_non_retryable_error() -> None:
    with pytest.raises(ModelProviderError, match="ANTHROPIC_API_KEY") as caught:
        AnthropicProvider(None).complete(REQUEST)

    assert caught.value.code == "provider_not_configured" and not caught.value.retryable
