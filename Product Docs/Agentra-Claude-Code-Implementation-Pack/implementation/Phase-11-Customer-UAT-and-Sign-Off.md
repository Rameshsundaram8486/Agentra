# Agentra Implementation Specification — Phase 11 — Customer UAT and Sign-Off

**Product:** Agentra — A Company Runs by Agents  
**Scope classification:** MVP — implement fifth  
**Status:** Planning specification; not yet implemented  
**Implementation rule:** Follow the repository's approved architecture and coding conventions. Do not invent integrations, credentials, business rules, or approvals.

## 1. Purpose and outcome

Coordinate customer validation and capture authorized acceptance or documented rejection against a specific solution version.

This phase must be implemented as a controlled workflow, not as a free-running chatbot. The workflow engine owns state transitions; agents produce proposals and outputs; application services enforce authorization, validation and approvals.

## 2. Primary agent and collaborating roles

- **UAT & Release Agent:** prepares UAT pack and coordinates status.
- **Customer tester/authorized approver:** executes or validates UAT and records decision.
- **Business Analyst Agent:** maps feedback to requirements.
- **Developer and QA Agents:** remediate and verify defects.
- **Project Owner Agent:** monitors UAT blockers and escalations.

## 3. Inputs and prerequisites

QA completion evidence, approved requirements baseline, release candidate/version, UAT environment, customer stakeholder list and acceptance policy.

## 4. Workflow

1. Verify required QA gates are satisfied.
2. Generate UAT scenarios from acceptance criteria and traceability.
3. Prepare UAT instructions and customer test pack.
4. Record test outcomes, evidence and feedback.
5. Classify feedback as defect, clarification, scope change or enhancement.
6. Route defects through development and QA retesting.
7. Track exceptions and outstanding issues.
8. Request sign-off from an authenticated authorized customer representative.
9. Link sign-off to the exact release candidate and requirements baseline.
10. Produce UAT completion report and handoff status for future Phase Twelve.

## 5. Deliverables and artifacts

UAT plan; scenario pack; execution records; feedback and defect register; retest evidence; exception list; customer sign-off/rejection record; UAT summary and detailed report.

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

An agent cannot fabricate or infer customer acceptance. Sign-off must be authenticated, version-specific and auditable. Scope changes must be routed to change control.

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

UAT scenarios trace to approved criteria; customer outcomes and issues are recorded; defects follow controlled remediation; sign-off is linked to exact versions; missing approval blocks completion.

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
