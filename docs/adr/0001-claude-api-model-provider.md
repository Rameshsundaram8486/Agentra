# ADR 0001 — Claude API as model provider

- **Status:** Accepted (2026-11-02)
- **Supersedes:** spec direction of Ollama (`qwen3:4b-instruct`) locally and private-GPU inference in production.

## Decision
All agents call the Claude API through `app/model_gateway`. Start every agent on `claude-opus-5-5` and tune `effort` per agent in `config/models.yaml`; consider cheaper models only where evals show quality holds. Enable the server-side refusal fallback and record the model that actually answered in each agent run.

## Consequences
- The gateway stays provider-neutral (principle 9), but only the Anthropic provider is built.
- Inference geography on the direct API is `global` or `us`; there is no UAE option. Customer contracts must allow processing outside the UAE.
- Harness conversations are append-only; no prefill, no `temperature`; effort is the main control.
