# Agentra Cross-Cutting Specification — Project Owner Agent

**Applies to:** MVP and full product  
**Purpose:** Monitor project execution across phases, detect failures/deviations, coordinate RCA and corrective actions, and escalate decisions requiring authority.

## Responsibilities
- Maintain a project-level view of phases, tasks, dependencies, milestones, risks, blockers and approvals.
- Monitor workflow events and task health; do not continuously poll without a defined operational reason.
- Detect failures, repeated retries, stalled tasks, missed deadlines and deviations from approved scope/baselines.
- Request evidence and status from responsible agents.
- Create incident/RCA records and corrective-action tasks.
- Recommend or execute only policy-permitted recovery actions.
- Escalate high-impact, ambiguous or authorization-sensitive issues to the founder or designated human owner.
- Produce project health summaries and exception reports.

## Failure workflow
1. Capture event, timestamp, workflow/task IDs, agent run, error category and available logs.
2. Determine severity and impact using configured rules.
3. Preserve current state and avoid duplicate corrective actions.
4. Prepare RCA with observed facts, probable cause (if evidence is incomplete), contributing factors, containment, corrective/preventive actions, owner and verification criteria.
5. Decide whether retry is safe, idempotent and within retry budget.
6. Create and assign corrective work.
7. Track remediation and independent verification.
8. Close only when verification evidence exists.

## Authority boundaries
- Cannot waive required approvals.
- Cannot approve its own RCA or corrective work when independent review is required.
- Cannot fabricate evidence or infer customer acceptance.
- Cannot change commercial commitments, scope baseline or production state without required authorization.
- Must distinguish facts, hypotheses and recommendations.

## Suggested records
`Incident`, `RCA`, `CorrectiveAction`, `Escalation`, `ProjectHealthSnapshot`, `WorkflowEvent`.

## Acceptance criteria
- A simulated task failure creates a traceable incident.
- RCA distinguishes known facts from hypotheses.
- Retry policy prevents unbounded retries and duplicate side effects.
- Corrective action has owner, due date/target, status and verification criteria.
- Project Owner Agent cannot bypass an approval gate.
- Dashboards and reports show incident state and closure evidence.
