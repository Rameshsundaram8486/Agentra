"""Resolves model, effort and limits per agent from config/models.yaml."""

from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.model_gateway.errors import ModelConfigError

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelProfile(_Strict):
    model: str
    effort: Effort
    max_tokens: int = Field(ge=1024, le=128_000)
    timeout_seconds: float = Field(gt=0, le=600)
    max_retries: int = Field(ge=0, le=5)
    refusal_fallback: bool


class ProfileOverride(_Strict):
    model: str | None = None
    effort: Effort | None = None
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    max_retries: int | None = None
    refusal_fallback: bool | None = None


class AgentOverride(ProfileOverride):
    tasks: dict[str, ProfileOverride] = Field(default_factory=dict)


class Pricing(_Strict):
    """US dollars per million tokens."""

    input: Decimal
    output: Decimal
    cache_write: Decimal
    cache_read: Decimal


class Budget(_Strict):
    monthly_usd: Decimal = Field(ge=0)


class ModelConfig(_Strict):
    version: int
    provider: Literal["anthropic"]
    defaults: ModelProfile
    agents: dict[str, AgentOverride] = Field(default_factory=dict)
    budget: Budget
    pricing_usd_per_mtok: dict[str, Pricing]

    @model_validator(mode="after")
    def _consistent(self) -> "ModelConfig":
        if not self.pricing_usd_per_mtok:
            raise ValueError("pricing_usd_per_mtok must list at least one model")
        profiles = [self.profile(key, task) for key, agent in self.agents.items() for task in [None, *agent.tasks]]
        models = {self.defaults.model} | {profile.model for profile in profiles}  # building them validates overrides
        unpriced = models - set(self.pricing_usd_per_mtok)
        if unpriced:
            raise ValueError(f"models without pricing: {sorted(unpriced)}")
        return self

    def profile(self, agent_key: str, task_key: str | None = None) -> ModelProfile:
        """Defaults, then the agent's overrides, then the task's."""
        agent = self.agents.get(agent_key)
        if agent is None:
            return self.defaults
        merged = {**self.defaults.model_dump(), **agent.model_dump(exclude_none=True, exclude={"tasks"})}
        task = agent.tasks.get(task_key) if task_key else None
        if task is not None:
            merged.update(task.model_dump(exclude_none=True))
        return ModelProfile.model_validate(merged)

    def pricing(self, model: str) -> tuple[Pricing, bool]:
        """Price for a model, and whether it is exact. Unknown models get the highest listed rates."""
        if model in self.pricing_usd_per_mtok:
            return self.pricing_usd_per_mtok[model], True
        return self.highest_pricing(), False

    def highest_pricing(self) -> Pricing:
        return max(self.pricing_usd_per_mtok.values(), key=lambda p: (p.output, p.input))


def load_model_config(path: Path) -> ModelConfig:
    try:
        with path.open(encoding="utf-8") as handle:
            return ModelConfig.model_validate(yaml.safe_load(handle))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ModelConfigError(f"{path.name}: {exc}") from exc
