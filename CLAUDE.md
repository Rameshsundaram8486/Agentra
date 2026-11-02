# Agentra — instructions for Claude Code

## Source of truth
- Product specs: `Product Docs/Agentra-Claude-Code-Implementation-Pack/` (README, Implementation-Roadmap-and-Architecture, Phase-01…13, Cross-Cutting-*) and `Product Docs/Agentra_Product_Overview.md`.
- Decisions that override the specs: `docs/adr/`.
- Read the relevant phase spec and cross-cutting specs before working on a phase.

## Working rules
- Do not implement anything until the user approves the plan for that increment. Propose plan and tests first.
- One phase / vertical slice at a time. MVP is Phases 7–11 plus Project Owner, reporting, governance. Do not build Phases 1–6, 12–13 until the MVP is accepted.
- Run the tests after each change; report files changed, tests run, results and remaining gaps.
- Never claim an integration, test, approval or deployment succeeded unless it was verified.
- Ask before destructive actions, external customer communication, production deployment or paid services.
- Do not modify `Product Docs/`.

## Architecture rules
- Modular monolith. Modules talk only through each other's `service.py`; never another module's tables.
- The workflow engine owns state. Neither the UI nor an LLM changes authoritative state directly; every transition goes through `app/modules/workflow` and records actor, reason, before/after.
- Agent output is untrusted until it passes `app/guardrails` (schema, grounding, forbidden claims, secrets). Guardrails are code, never prompt text.
- Agents never approve. Approvals are human, server-side, and bind to artifact version id + content sha256. No self-approval where independent review is required.
- Persist before side effects; use idempotency keys and the outbox for external actions; bounded retries.
- Code execution and computer use run only in sandbox VMs (`app/harness/sandbox`), never on the Agentra host. No production tenants in the MVP.
- Model calls only through `app/model_gateway`. Provider: Claude API, model `claude-opus-5-5`, effort set per agent in `config/models.yaml`. Computer use uses `computer_toolset_20260801`.
- Agent definitions, prompts, schemas, workflows and policies are declarative and versioned under `config/`.
- Secrets never in source, prompts, logs or generated documents. Use synthetic data locally.

## Stack
Python 3.12+, FastAPI, SQLAlchemy + Alembic, PostgreSQL (+ pgvector), pytest. Plain HTML/CSS/JS in `web/`. No Docker in the first iteration; local sandbox VMs use Hyper-V.
