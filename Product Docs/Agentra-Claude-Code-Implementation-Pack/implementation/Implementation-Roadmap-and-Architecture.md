# Agentra — Implementation Roadmap and Architecture

## Product name
**Agentra — A Company Runs by Agents**

## Architecture principle
Build a governed workflow platform, not a collection of independent chatbots. The workflow engine owns authoritative state, agents perform bounded tasks, application services enforce rules, and the audit layer records consequential actions.

## Proposed development stack
- Python and FastAPI for backend APIs.
- HTML/CSS/JavaScript for the first web UI, unless a later decision selects another frontend.
- SQLite for local prototype; preserve a migration path to PostgreSQL.
- Ollama for local model experiments; model calls behind a provider-neutral gateway.
- Git and private GitHub for version control.
- pytest for automated testing.
- Durable queue and production deployment technology selected after workflow and operational requirements are validated.
- Do not require Docker for the first development iteration. Do not interrupt existing Docker/Ollama/Saha projects.

## Logical layers
1. **Company Control Center:** dashboard, project workspace, task detail, artifact review, approvals and agent configuration.
2. **Application API:** authentication/authorization integration, request validation, business services and event handling.
3. **Workflow Engine:** workflow definitions, states, dependencies, retries, approvals and resumption.
4. **Agent Runtime:** agent registry, bounded context, tool execution, output validation and execution records.
5. **Data & Memory:** projects, tasks, artifact metadata, audit records and scoped approved knowledge.
6. **Model Gateway:** provider-neutral interface, routing, prompt/schema versions, limits, errors and usage tracking.

## MVP scope — implement first
- Phase Seven: Business Analysis and Requirements.
- Phase Eight: Solution Architecture and Technical Design.
- Phase Nine: Development and Implementation.
- Phase Ten: Quality Assurance and Testing.
- Phase Eleven: Customer UAT and Sign-Off.
- Cross-cutting: Project Owner Agent for delivery oversight, reporting/documentation, human governance/autonomy, auditability and failure handling.

## Full product scope — later
- Phase One: Sales and Lead Generation.
- Phase Two: Meeting Scheduling and Customer Discovery.
- Phase Three: Technical and Commercial Proposal.
- Phase Four: Customer Presentation and Negotiation.
- Phase Five: Project Award and PO Validation.
- Phase Six: Project Kickoff and Governance.
- Phase Twelve: Production Go-Live.
- Phase Thirteen: Project Closure.
- Expand Project Owner Agent to end-to-end company oversight and expand reporting/governance to the entire lifecycle.

## Recommended implementation sequence
1. Inspect repository and agree architecture/data model.
2. Create core project, phase, workflow run, task, agent run, artifact/version, review, approval, audit event, defect and incident/RCA entities.
3. Implement explicit workflow state transitions and server-side authorization.
4. Implement artifact versioning and approval linkage.
5. Implement a small end-to-end Phase Seven → Eight → Nine → Ten → Eleven demonstration workflow.
6. Add QA defect loop and UAT sign-off.
7. Add Project Owner monitoring, RCA and reports.
8. Add tests for failure, retry, resume, unauthorized action and version mismatch.
9. Validate with a representative synthetic project.
10. Only after MVP evaluation, add full product phases.

## Repository principles
- Modular monolith first; do not split into microservices prematurely.
- Keep LLM provider code behind a gateway.
- Keep agent definitions declarative and versioned.
- Persist before performing consequential side effects.
- Use idempotency for retries and external actions.
- Treat all model output as untrusted until schema and policy validation passes.
- Do not let the UI or LLM directly mutate authoritative state.
- Store artifact content separately from metadata where appropriate.
- Avoid hardcoded customer data and secrets.
- Do not claim integrations are implemented until tested against authorized environments.

## Claude Code workflow
Before implementation, instruct Claude Code to inspect the repository and relevant specifications, report its proposed plan, implement one small increment at a time, run tests, and summarize files changed and remaining gaps. Do not implement future product phases as if they were part of the MVP.
