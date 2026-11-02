# Agentra Implementation Specification — Phase 01 — Sales and Lead Generation

**Product:** Agentra — A Company Runs by Agents  
**Scope classification:** Full product — post-MVP  
**Status:** Planning specification; not yet implemented  
**Implementation rule:** Follow the repository's approved architecture and coding conventions. Do not invent integrations, credentials, business rules, or approvals.

## 1. Purpose and outcome

Create a traceable pipeline of suitable prospects and qualified opportunities using approved research and outreach channels.

This phase must be implemented as a controlled workflow, not as a free-running chatbot. The workflow engine owns state transitions; agents produce proposals and outputs; application services enforce authorization, validation and approvals.

## 2. Primary agent and collaborating roles

- **Sales / Lead Generation Agent:** researches prospects, drafts tailored outreach, classifies responses and recommends qualification.
- **Market Research Agent:** supplies evidence about industries, organizations and relevant business needs.
- **Company Orchestrator:** starts and coordinates the lead workflow.
- **Human sales owner:** approves campaign policies, sensitive outreach and commercial commitments.

## 3. Inputs and prerequisites

Target market, service catalogue, ideal customer profile, approved outreach policy, approved message templates, channel permissions, suppression/opt-out list and available public/company information.

## 4. Workflow

1. Create a campaign using approved target criteria and channel policy.
2. Research a prospect and preserve source/evidence links.
3. Score fit using configurable criteria; show rationale and uncertainty.
4. Draft personalized outreach; apply policy and duplicate-contact checks.
5. Send only through authorized integrations and within approved limits.
6. Record delivery, response, opt-out and follow-up status.
7. Classify replies and create an opportunity when qualification criteria are met.
8. Route interested prospects to Phase Two; route ambiguous or sensitive replies to a human.

## 5. Deliverables and artifacts

Prospect record; source/evidence notes; qualification assessment; outreach draft and delivery log; response classification; opportunity record; campaign summary.

Each artifact must have a stable ID, project/workflow linkage, version, creator, creation timestamp, status, source references and review/approval history where applicable. Store artifact metadata in the operational database and content in the configured artifact store.

## 6. State model and transitions

Use explicit states appropriate to the phase. At minimum, distinguish:
- `not_started`
- `ready`
- `in_progress`
- `waiting_for_input`
- `waiting_for_review`
- `changes_requested`
- `blocked`
- `failed`
- `completed`
- `cancelled`

Do not allow a UI or LLM to directly change authoritative workflow state. Validate every transition in a backend service. Record actor, timestamp, previous state, new state and reason.

## 7. Validation and quality gates

No outreach before channel authorization and policy checks. Respect opt-outs, applicable privacy/marketing laws, provider rules and rate limits. Do not scrape or automate prohibited actions. No invented prospect facts. Require review for uncertain, sensitive or high-volume campaigns.

## 8. Failure handling and RCA

For any failed or blocked task:
1. Persist the error, current workflow state and relevant execution evidence.
2. Notify the Project Owner Agent / central oversight service.
3. Classify severity and customer/business impact.
4. Prepare an RCA record with observed facts, likely cause, contributing factors, containment, corrective action, owner and verification criteria.
5. Retry only when the failure is retryable and the retry policy permits it.
6. Escalate decisions requiring human authorization.
7. Close the incident only after the corrective action is verified.

Never invent a root cause when evidence is insufficient; mark it as unknown or probable and list the evidence needed.

## 9. Reporting requirements

Generate both:
- **Executive summary:** status, outcome, decisions, blockers, risks and next actions.
- **Detailed report:** inputs, activities, outputs, versions, review comments, evidence, defects, state transitions and approvals.

Reports must be based on recorded workflow data and artifacts, not only on an agent's narrative.

## 10. Security, permissions and human governance

- Apply least-privilege access to project data, artifacts and tools.
- Validate permissions server-side for every consequential action.
- Keep secrets out of prompts, logs, source control and generated documents.
- Record approvals against the exact artifact version and an authenticated approver.
- Agents cannot approve their own work or fabricate customer acceptance.
- Use synthetic data in local development unless real data is explicitly approved for the environment.
- Require explicit human approval for scope, commercial, customer commitment, production or other high-impact changes as configured by policy.

## 11. Data model considerations

Define or reuse appropriate entities rather than duplicating records. Typical links include:
- Project → phase/workflow run → tasks → agent runs
- Task → input references → output artifacts
- Artifact → versions → reviews → approvals
- Defect/issue → requirement → test case → fix task → retest evidence
- Failure/incident → RCA → corrective actions → verification

Use database migrations for schema changes and preserve referential integrity.

## 12. API and UI expectations

Expose backend endpoints only where needed by the interface or integrations. Validate request schemas and authorization. The UI should show phase status, assigned agent, task activity, deliverables, blockers, reviews, approvals and reports. Do not present mock values as real execution state.

## 13. Testing requirements

Implement:
- Unit tests for domain rules and validation.
- Workflow tests for successful and rejected paths.
- Permission tests for unauthorized actions.
- Failure/retry/resume tests.
- Versioning and approval-linkage tests.
- Tests that verify reports reflect persisted records.
- Regression tests for connected phases.

## 14. Acceptance criteria

A user can configure an approved campaign, inspect prospect evidence, review or authorize messages, track replies and opt-outs, create a qualified opportunity and audit every action. Tests cover duplicate prevention, opt-out suppression, invalid contacts, failed delivery and ambiguous replies.

## 15. Claude Code implementation instructions

1. Inspect the existing repository before editing.
2. Read the root product architecture and relevant phase specifications.
3. Summarize the current implementation and identify gaps before making changes.
4. Implement in small, testable increments.
5. Do not overwrite unrelated files or change another project.
6. Do not add external services or dependencies without explaining the need.
7. Keep provider/model-specific code behind interfaces.
8. Add tests and run the relevant test suite.
9. Update the README and architecture notes for material changes.
10. Report changed files, decisions, tests run, results, known limitations and next steps.
11. Do not claim that an integration, test, approval or deployment succeeded unless it was actually verified.
