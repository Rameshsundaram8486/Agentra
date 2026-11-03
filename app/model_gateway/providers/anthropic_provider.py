"""Claude API provider (Anthropic SDK).

- Effort is always sent (claude-opus-5-5 defaults to medium otherwise); thinking is not sent, it is always on.
- Structured output through output_config.format, so the reply is one JSON text block.
- Refusal fallback through the server-side `fallbacks: "default"` beta; the model that answered is read from
  the response and usage.iterations, never assumed.
- The system prompt is marked for prompt caching; it is identical across runs of the same prompt version.
- Streaming, so long answers are not cut off by the non-streaming request timeout.
"""

from typing import Any

import anthropic

from app.model_gateway.errors import ModelProviderError
from app.model_gateway.providers.base import Attempt, ModelRequest, ModelResponse, TokenUsage

FALLBACK_BETA = "server-side-fallback-2026-07-01"

_RETRYABLE_STATUS = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.OverloadedError,
    anthropic.ServiceUnavailableError,
    anthropic.DeadlineExceededError,
)


def _usage(source: Any) -> TokenUsage:
    return TokenUsage(
        input_tokens=source.input_tokens or 0,
        output_tokens=source.output_tokens or 0,
        cache_creation_input_tokens=getattr(source, "cache_creation_input_tokens", 0) or 0,
        cache_read_input_tokens=getattr(source, "cache_read_input_tokens", 0) or 0,
    )


def _translate(exc: Exception) -> ModelProviderError:
    message = f"{type(exc).__name__}: {getattr(exc, 'message', None) or exc}"
    if isinstance(exc, anthropic.APIConnectionError):  # includes timeouts
        return ModelProviderError(message, code="provider_unreachable", retryable=True)
    if isinstance(exc, anthropic.RateLimitError):
        return ModelProviderError(message, code="rate_limited", retryable=True)
    if isinstance(exc, _RETRYABLE_STATUS):
        return ModelProviderError(message, code="provider_unavailable", retryable=True)
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return ModelProviderError(message, code="provider_auth", retryable=False)
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return ModelProviderError(message, code="provider_unavailable", retryable=True)
        return ModelProviderError(message, code="bad_request", retryable=False)
    return ModelProviderError(message, code="provider_error", retryable=False)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None, *, client: Any = None) -> None:
        """`client` is for tests; normally the SDK client is built from the key in settings."""
        if client is None and not api_key:
            self._client = None
        else:
            self._client = client or anthropic.Anthropic(api_key=api_key)

    def build_params(self, request: ModelRequest) -> dict[str, Any]:
        output_config: dict[str, Any] = {"effort": request.effort}
        if request.output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": request.output_schema}
        params: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": [{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": request.user}],
            "output_config": output_config,
        }
        if request.refusal_fallback:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def complete(self, request: ModelRequest) -> ModelResponse:
        if self._client is None:
            raise ModelProviderError(
                "ANTHROPIC_API_KEY is not set; add it to .env", code="provider_not_configured", retryable=False
            )
        client = self._client.with_options(timeout=request.timeout_seconds, max_retries=request.max_retries)
        try:
            with client.beta.messages.stream(**self.build_params(request)) as stream:
                message = stream.get_final_message()
                request_id = getattr(stream, "request_id", None)
        except anthropic.AnthropicError as exc:
            raise _translate(exc) from exc
        return self.to_response(message, request.model, request_id)

    @staticmethod
    def to_response(message: Any, requested_model: str, request_id: str | None = None) -> ModelResponse:
        iterations = [
            entry for entry in (message.usage.iterations or []) if entry.type in ("message", "fallback_message")
        ]
        if iterations:
            attempts = tuple(Attempt(entry.model or requested_model, _usage(entry)) for entry in iterations)
        else:
            attempts = (Attempt(message.model, _usage(message.usage)),)
        refusal_category = None
        if message.stop_reason == "refusal" and message.stop_details is not None:
            refusal_category = message.stop_details.category or "unspecified"
        return ModelResponse(
            text="".join(block.text for block in message.content if block.type == "text"),
            model=message.model,
            stop_reason=message.stop_reason,
            refusal_category=refusal_category,
            fallback_used=any(entry.type == "fallback_message" for entry in iterations),
            attempts=attempts,
            request_id=request_id or getattr(message, "_request_id", None),
        )
