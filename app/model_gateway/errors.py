"""Normalised model errors. Callers decide on retries from `retryable`, never from provider exception types."""


class ModelGatewayError(Exception):
    """Base class. `code` is a stable, short identifier recorded on the agent run."""

    code = "model_error"
    retryable = False


class ModelProviderError(ModelGatewayError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class BudgetExceededError(ModelGatewayError):
    """The monthly model spending cap would be exceeded. Not retryable until the cap or the month changes."""

    code = "budget_exceeded"


class ModelConfigError(ValueError):
    """config/models.yaml is invalid. Fails startup."""
