# ADR 0004 — Computer use inside sandbox VMs

- **Status:** Accepted (2026-11-02)

## Decision
Computer use (`computer_toolset_20260801` on Claude Opus 5.5) is allowed for UI-only work, mainly SharePoint / Power Platform configuration with no API, exploratory UI testing and UAT walkthrough screenshots. It runs only in Desktop sandbox VMs. Preference order: API/CLI → Playwright script → computer use.

## Guardrails
- Action classes in `config/policies/computer_use.yaml`: look (autonomous), edit in dev/test tenant (within budget), commit clicks such as Save/Publish/Delete/Share (human approval), off-allowlist navigation and production tenants (blocked).
- The harness signs in before handing over control; the model never sees credentials.
- On-screen content is untrusted input. Every action stores before/after screenshots as evidence.
- Never used to record customer sign-off.
