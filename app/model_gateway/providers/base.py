"""Provider interface. Providers translate one request into one response; they never touch the database."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ModelRequest:
    model: str
    effort: str
    max_tokens: int
    system: str
    user: str
    output_schema: dict[str, Any] | None
    refusal_fallback: bool
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True)
class Attempt:
    """One model's attempt at the request. A declined attempt followed by a fallback gives two."""

    model: str
    usage: TokenUsage


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model: str  # the model that produced the returned message
    stop_reason: str | None
    refusal_category: str | None = None
    fallback_used: bool = False
    attempts: tuple[Attempt, ...] = field(default_factory=tuple)
    request_id: str | None = None

    @property
    def usage(self) -> TokenUsage:
        return TokenUsage(
            input_tokens=sum(a.usage.input_tokens for a in self.attempts),
            output_tokens=sum(a.usage.output_tokens for a in self.attempts),
            cache_creation_input_tokens=sum(a.usage.cache_creation_input_tokens for a in self.attempts),
            cache_read_input_tokens=sum(a.usage.cache_read_input_tokens for a in self.attempts),
        )


class Provider(Protocol):
    name: str

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Raises ModelProviderError for anything that did not produce a response."""
        ...
