"""Scripted provider for tests and offline demos. Records every request; never calls a network."""

from collections.abc import Callable, Iterable
from typing import Any

from app.model_gateway.providers.base import Attempt, ModelRequest, ModelResponse, TokenUsage

Script = ModelResponse | Exception | Callable[[ModelRequest], ModelResponse]


def fake_response(
    text: str,
    *,
    model: str = "claude-opus-5-5",
    stop_reason: str = "end_turn",
    usage: TokenUsage = TokenUsage(input_tokens=3_000, output_tokens=2_000),
    **kwargs: Any,
) -> ModelResponse:
    attempts = kwargs.pop("attempts", (Attempt(model, usage),))
    return ModelResponse(text=text, model=model, stop_reason=stop_reason, attempts=attempts, request_id="req_fake", **kwargs)


class FakeProvider:
    name = "fake"

    def __init__(self, script: Iterable[Script] = ()) -> None:
        self._script = list(script)
        self.requests: list[ModelRequest] = []

    def add(self, *items: Script) -> None:
        self._script.extend(items)

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self._script:
            raise AssertionError("FakeProvider has no scripted response left")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(request) if callable(item) else item
