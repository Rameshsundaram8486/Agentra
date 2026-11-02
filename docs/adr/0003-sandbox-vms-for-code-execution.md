# ADR 0003 — Sandbox VMs for code execution

- **Status:** Accepted (2026-11-02)

## Decision
Agent code execution (Phase 9 development, Phase 10 automated tests) runs only inside disposable VMs created from versioned images: Hyper-V locally, Azure VMs (UAE North) in production. An in-VM `sandbox-agent` connects outward to Agentra; VMs have no inbound ports, an egress allowlist, one customer per VM, short-lived scoped credentials, time/action limits and a kill switch.

## Consequences
- Nothing an agent runs touches the Agentra host.
- VM infrastructure is built after Phases 7–8 work end to end and before Phase 9.
