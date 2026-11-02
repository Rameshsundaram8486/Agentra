# Agentra Implementation Specification — Phase 02 — Meeting Scheduling and Customer Discovery

**Product:** Agentra — A Company Runs by Agents  
**Scope classification:** Full product — post-MVP  
**Status:** Planning specification; not yet implemented  
**Implementation rule:** Follow the repository's approved architecture and coding conventions. Do not invent integrations, credentials, business rules, or approvals.

## 1. Purpose and outcome

Schedule customer discovery meetings and convert conversations into reviewable, structured business inputs.

This phase must be implemented as a controlled workflow, not as a free-running chatbot. The workflow engine owns state transitions; agents produce proposals and outputs; application services enforce authorization, validation and approvals.

## 2. Primary agent and collaborating roles

- **Opportunity & Discovery Agent:** prepares agenda, questions and follow-up.
- **Scheduling Agent/service:** checks authorized calendar availability and creates Teams meetings.
- **Voice Meeting Agent:** participates only when clearly disclosed and authorized; captures discussion and structured notes.
- **Business Analyst Agent:** may review requirements extracted from the meeting.

## 3. Inputs and prerequisites

Qualified opportunity, customer contacts, authorized calendar access, participant availability, time zone, meeting purpose, approved disclosure/consent wording and discovery template.

## 4. Workflow

1. Propose available times and confirm the selected slot.
2. Create the Teams meeting using authorized Microsoft integration.
3. Prepare agenda and questions based on opportunity context.
4. Join/participate only within supported and authorized meeting capabilities; clearly disclose AI participation and recording/transcription status.
5. Produce transcript or notes only according to consent, retention and access policy.
6. Generate executive summary, detailed MoM, decisions, action items, owners, dates, requirements inputs and unresolved questions.
7. Ask a human/customer to validate uncertain statements.
8. Route approved discovery outputs to Phase Three.

## 5. Deliverables and artifacts

Meeting invite; agenda; MoM; action register; decision log; preliminary requirements; assumptions, constraints and open questions; follow-up communication draft.

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

Never imply the voice agent is human. Respect consent, recording, privacy, retention and meeting-platform policies. Do not create meetings without authorized calendar permissions. Distinguish direct customer statements from agent inferences.

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

The system can schedule a meeting, maintain its metadata, generate structured notes from available authorized input, track action items and route the reviewed discovery pack forward. Tests cover time zones, conflicts, rescheduling, consent/recording disabled, missing transcript and uncertain requirements.

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
