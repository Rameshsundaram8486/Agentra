# Agentra Cross-Cutting Specification — Reporting and Documentation

**Applies to:** MVP and full product

## Purpose
Generate consistent executive summaries and detailed reports from authoritative workflow records, artifacts, test evidence, approvals and audit events.

## Report layers
### Executive summary
- Overall status and phase.
- Outcome and progress against baseline.
- Decisions required.
- Key risks, blockers and dependencies.
- Recent milestones and next actions.
- Owner and due date for each action.

### Detailed report
- Scope and inputs.
- Workflow/task IDs and state transitions.
- Agent activities and outputs.
- Artifact versions and source references.
- Review comments and disposition.
- Requirement/test traceability.
- Defects, incidents and RCA.
- Approvals and exact versions approved.
- Exceptions, limitations and unresolved questions.

## Required MVP reports
- Requirements summary and detailed BRD/traceability report.
- Architecture/design summary and detailed design pack.
- Development progress and implementation report.
- Test execution, coverage, defects and QA completion report.
- UAT summary, outstanding issues and sign-off report.
- Project health and failure/RCA reports.

## Full product reports
Add lead pipeline, campaign outcomes, discovery/MoM, proposal and estimate, negotiation, PO validation, kickoff/RACI, release/go-live and closure reports.

## Rules
- Reports are generated from persisted records; an LLM may explain them but must not invent status or metrics.
- Include generated-at timestamp, reporting period, project ID, report version and data sources.
- Clearly label estimates, assumptions and incomplete data.
- Maintain version history for formal reports.
- Restrict customer visibility according to project permissions.
- Avoid including secrets or unnecessary personal information.

## Acceptance criteria
A report can be regenerated from the same source records; figures reconcile to the database; artifact and approval links are valid; incomplete information is explicitly labelled; report versions are auditable.
