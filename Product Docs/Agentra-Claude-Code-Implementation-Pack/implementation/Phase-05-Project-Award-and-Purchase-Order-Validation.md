# Agentra Implementation Specification — Phase 05 — Project Award and Purchase Order Validation

**Product:** Agentra — A Company Runs by Agents  
**Scope classification:** Full product — post-MVP  
**Status:** Planning specification; not yet implemented  
**Implementation rule:** Follow the repository's approved architecture and coding conventions. Do not invent integrations, credentials, business rules, or approvals.

## 1. Purpose and outcome

Confirm that the project has sufficient commercial authorization before delivery initiation.

This phase must be implemented as a controlled workflow, not as a free-running chatbot. The workflow engine owns state transitions; agents produce proposals and outputs; application services enforce authorization, validation and approvals.

## 2. Primary agent and collaborating roles

- **Project Initiation / Commercial Control Agent:** compares award and PO evidence to the approved proposal.
- **Proposal Agent:** clarifies proposal terms.
- **Project Manager Agent:** receives validated initiation package.
- **Human commercial owner:** resolves discrepancies and authorizes exceptions.

## 3. Inputs and prerequisites

Approved proposal and version, customer award/acceptance evidence, PO document, contract/terms where applicable, authorized signatories and project start conditions.

## 4. Workflow

1. Register award evidence and PO document.
2. Extract relevant values with source locations and confidence.
3. Compare scope, price, currency, tax, dates, quantities, payment terms and customer entity.
4. Flag missing fields and discrepancies.
5. Route discrepancies for resolution; do not infer approval.
6. Record authorized commercial validation.
7. Create the project initiation package and release Phase Six.

## 5. Deliverables and artifacts

Award record; PO validation checklist; discrepancy report; approval/exception record; project initiation package.

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

OCR/LLM extraction is not legal validation. Require human review for material discrepancies and policy-defined commercial authorization. Never initiate delivery based only on an unverified verbal award if PO/contract controls require documents.

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

The platform compares PO data to the exact proposal version, highlights mismatches with evidence, records the decision and blocks project initiation until mandatory conditions are satisfied.

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
