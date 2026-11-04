"""Builds report data from records. Pure and deterministic: the same records always give the same data, with no
clock reads, no model calls and stable ordering. Missing information is labelled, never filled in.
An agent may later narrate a report; it will never supply its figures.
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

NO_DUE_DATE = "No due date set"
LIMITATIONS = [
    "Design and test columns of the traceability matrix are filled from Phases 8 and 10.",
    "Defects: not applicable until Phase 10 (testing).",
    "Due dates are not tracked for decisions, reviews or change requests yet; only incident corrective actions have target dates.",
]


@dataclass(frozen=True)
class ReportInputs:
    """Views of the records a report reads, gathered by the reporting service through each module's service."""

    project: Any
    phase: Any  # PhaseRunView of the report's phase
    phase_history: list[Any] = field(default_factory=list)
    task_histories: Mapping[uuid.UUID, list[Any]] = field(default_factory=dict)
    documents: list[Any] = field(default_factory=list)  # ArtifactDetail: briefs and source documents
    baseline: Any = None  # ArtifactDetail of the requirements baseline
    approvals: Mapping[uuid.UUID, Any] = field(default_factory=dict)  # artifact id -> ArtifactApprovals
    artifact_titles: Mapping[uuid.UUID, tuple[str, str]] = field(default_factory=dict)  # id -> (title, type title)
    decisions: list[Any] = field(default_factory=list)
    requirements: Any = None
    traceability: Any = None
    change_requests: list[Any] = field(default_factory=list)
    runs: list[Any] = field(default_factory=list)
    incidents: list[Any] = field(default_factory=list)
    names: Mapping[uuid.UUID, str] = field(default_factory=dict)


def ts(value: datetime | None) -> str | None:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC") if value else None


def label(value: str | None) -> str:
    return (value or "").replace("_", " ")


def data_as_of(inputs: ReportInputs) -> datetime | None:
    """The newest record the report includes."""
    stamps: list[datetime] = [inputs.phase.updated_at, *(t.updated_at for t in inputs.phase.tasks)]
    for detail in [*inputs.documents, *([inputs.baseline] if inputs.baseline else [])]:
        stamps += [version.created_at for version in detail.versions]
    stamps += [a.created_at for approvals in inputs.approvals.values() for a in approvals.history]
    for decision in inputs.decisions:
        stamps += [decision.created_at, *(o.created_at for o in decision.outcomes)]
    for request in inputs.change_requests:
        stamps += [request.created_at, *(e.created_at for e in request.events)]
    for run in inputs.runs:
        stamps += [run.created_at, *([run.finished_at] if run.finished_at else [])]
    for incident in inputs.incidents:
        stamps += [incident.opened_at, *(e.created_at for e in incident.events)]
    return max(stamps) if stamps else None


def _approval_of(inputs: ReportInputs, artifact_id: uuid.UUID, version_id: uuid.UUID) -> Any:
    approvals = inputs.approvals.get(artifact_id)
    return next((a for a in approvals.history if a.artifact_version_id == version_id), None) if approvals else None


def _baseline(inputs: ReportInputs) -> dict[str, Any] | None:
    view = inputs.requirements
    if view is None:
        return None
    approval = _approval_of(inputs, view.artifact_id, view.version_id)
    rows = inputs.traceability.rows if inputs.traceability else []
    return {
        "title": view.artifact_title,
        "version_no": view.version_no,
        "approval_status": view.approval_status,
        "approved": (
            {"by": approval.approver_name, "at": ts(approval.created_at), "sha256": approval.content_sha256}
            if approval and approval.decision == "approved"
            else None
        ),
        "locked": view.locked,
        "change_request": view.change_request,
        "counts": dict(view.counts),
        "item_count": len(view.items),
        "traced": {"rows": len(rows), "with_objective": sum(1 for r in rows if r.objectives)},
    }


def _next_actions(inputs: ReportInputs, baseline: dict[str, Any] | None) -> list[dict[str, str]]:
    actions = []
    for decision in sorted(inputs.decisions, key=lambda d: d.created_at):
        if decision.status == "open":
            actions.append({"action": f"Answer: {decision.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    if baseline and baseline["approval_status"] in ("pending", "changes_requested", "rejected"):
        actions.append({
            "action": f"Review and approve {baseline['title']} v{baseline['version_no']} ({label(baseline['approval_status'])})",
            "owner": "Reviewer or owner (not its author)",
            "due": NO_DUE_DATE,
        })
    for request in sorted(inputs.change_requests, key=lambda r: r.cr_id):
        if request.status == "open":
            missing = [label(r) for r in request.required_roles if r not in request.approved_roles]
            actions.append({"action": f"Decide {request.cr_id}: {request.title}", "owner": " and ".join(missing), "due": NO_DUE_DATE})
        elif request.status == "approved":
            actions.append({"action": f"Apply {request.cr_id}: {request.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    for incident in sorted(inputs.incidents, key=lambda i: i.incident_id):
        if incident.status == "open":
            actions.append({"action": f"Resolve {incident.incident_id}: {incident.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
        elif incident.status == "resolved" and incident.rca:
            actions.append({
                "action": f"Verify and close {incident.incident_id}: {incident.rca.corrective_action}",
                "owner": f"{incident.rca.action_owner_name or 'Action owner'}; closed by someone other than {incident.rca.resolved_by_name or 'the resolver'}",
                "due": incident.rca.target_date.isoformat(),
            })
    for task in inputs.phase.tasks:
        if task.state == "waiting_for_input":
            actions.append({"action": f"Provide input for: {task.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    return actions


def _milestones(inputs: ReportInputs) -> list[dict[str, str]]:
    events: list[tuple[datetime, str]] = []
    if inputs.baseline:
        for version in inputs.baseline.versions:
            events.append((version.created_at, f"{inputs.baseline.title} v{version.version_no}: {version.change_summary}"))
    for approvals in inputs.approvals.values():
        for a in approvals.history:
            title = inputs.artifact_titles.get(a.artifact_id, ("document", ""))[0]
            events.append((a.created_at, f"{title} v{a.version_no} {label(a.decision)} by {a.approver_name or 'a reviewer'}"))
    for request in inputs.change_requests:
        for e in request.events:
            what = "applied in a new version" if e.event == "applied" else f"{e.event} as {label(e.role)} by {e.actor_name or 'someone'}"
            events.append((e.created_at, f"{request.cr_id} {what}"))
    for task in inputs.phase.tasks:
        if task.state == "completed":
            events.append((task.updated_at, f"Task completed: {task.title}"))
    events.sort(key=lambda event: (event[0], event[1]), reverse=True)
    return [{"at": ts(at), "what": what} for at, what in events[:12]]


def _risks(inputs: ReportInputs) -> dict[str, Any]:
    items = inputs.requirements.items if inputs.requirements else []
    return {
        "open_questions": [{"id": i.item_id, "title": i.title} for i in items if i.kind == "open_question"],
        "dependencies": [{"id": i.item_id, "title": i.title} for i in items if i.kind == "dependency"],
        "assumptions": sum(1 for i in items if i.kind == "assumption" or i.label == "assumption"),
        "blocked_tasks": [{"title": t.title, "state": label(t.state)} for t in inputs.phase.tasks if t.state in ("blocked", "failed")],
        "incidents": [
            {"id": i.incident_id, "title": i.title, "severity": i.severity, "status": i.status}
            for i in sorted(inputs.incidents, key=lambda i: i.incident_id)
            if i.status != "closed"
        ],
        "trace_gaps": list(inputs.traceability.gaps) if inputs.traceability else [],
        "rows_with_gaps": sum(1 for r in inputs.traceability.rows if r.gaps) if inputs.traceability else 0,
    }


def _common(inputs: ReportInputs) -> dict[str, Any]:
    project = inputs.project
    return {
        "project": {"id": str(project.id), "code": project.code, "name": project.name, "customer": project.customer_name},
        "period": {"from": ts(project.created_at), "to": ts(data_as_of(inputs))},
        "phase": {
            "number": inputs.phase.phase,
            "name": inputs.phase.name,
            "state": label(inputs.phase.state),
            "tasks": [{"title": t.title, "state": label(t.state), "agent": label(t.agent) if t.agent else "People"} for t in inputs.phase.tasks],
        },
    }


def summary_data(inputs: ReportInputs) -> dict[str, Any]:
    baseline = _baseline(inputs)
    decisions = sorted(inputs.decisions, key=lambda d: d.created_at)
    return {
        **_common(inputs),
        "baseline": baseline,
        "decisions_waiting": [
            {"title": d.title, "raised_by": d.raised_by_name, "raised_at": ts(d.created_at)} for d in decisions if d.status == "open"
        ],
        "decisions_deferred": [{"title": d.title} for d in decisions if d.status == "deferred"],
        "risks": _risks(inputs),
        "milestones": _milestones(inputs),
        "next_actions": _next_actions(inputs, baseline),
        "limitations": LIMITATIONS,
    }


def _names(inputs: ReportInputs, user_id: uuid.UUID | None) -> str:
    return inputs.names.get(user_id, "unknown") if user_id else "unknown"


def _versions(inputs: ReportInputs, detail: Any) -> list[dict[str, Any]]:
    out = []
    for v in sorted(detail.versions, key=lambda v: v.version_no):
        approval = inputs.approvals.get(detail.id)
        decisions = [a for a in (approval.history if approval else []) if a.artifact_version_id == v.id]
        out.append({
            "version_no": v.version_no,
            "sha256": v.content_sha256,
            "author": _names(inputs, v.author_id),
            "at": ts(v.created_at),
            "change_summary": v.change_summary,
            "sources": list(v.source_refs),
            "reviews": [
                {"decision": label(a.decision), "by": a.approver_name, "at": ts(a.created_at), "comment": a.comment, "sha256": a.content_sha256}
                for a in sorted(decisions, key=lambda a: a.created_at)
            ],
        })
    return out


def _history(inputs: ReportInputs, rows: Iterable[Any]) -> list[dict[str, Any]]:
    return [
        {"from": label(r.from_state), "to": label(r.to_state), "by": _names(inputs, r.actor_id), "at": ts(r.occurred_at), "reason": r.reason}
        for r in rows
    ]


def detailed_data(inputs: ReportInputs) -> dict[str, Any]:
    view = inputs.requirements
    items = view.items if view else []
    return {
        **summary_data(inputs),
        "phase_history": _history(inputs, inputs.phase_history),
        "tasks": [
            {"title": t.title, "state": label(t.state), "history": _history(inputs, inputs.task_histories.get(t.id, []))}
            for t in inputs.phase.tasks
        ],
        "inputs": [
            {"title": d.title, "type": d.type_title, "versions": _versions(inputs, d)}
            for d in sorted(inputs.documents, key=lambda d: (d.artifact_type, d.title))
        ],
        "baseline_versions": _versions(inputs, inputs.baseline) if inputs.baseline else [],
        "review_responses": [{"comment": r.comment, "response": r.response} for r in (view.review_responses if view else [])],
        "summary_text": view.summary if view else None,
        "requirement_items": [
            {
                "id": i.item_id,
                "kind": label(i.kind),
                "title": i.title,
                "statement": i.statement,
                "label": label(i.label),
                "status": i.status,
                "priority": label(i.priority),
                "criteria": [f"{i.item_id}.AC{n}: {c}" for n, c in enumerate(i.acceptance_criteria, start=1)],
                "sources": [
                    f'Decision "{s.name}" ({s.answer or "not answered"})' if s.type == "decision" else f'{s.name}: "{" ".join(s.quote.split())}"'
                    for s in i.sources
                ],
                "related": list(i.related),
                "flags": [f"{f.check}: {f.message}" for f in i.quality_flags],
            }
            for i in items
        ],
        "traceability": [
            {
                "id": r.item_id,
                "title": r.title,
                "status": r.status,
                "objectives": list(r.objectives),
                "stories": list(r.user_stories),
                "criteria": list(r.acceptance_criteria),
                "design": r.design,
                "tests": r.tests,
                "gaps": list(r.gaps),
            }
            for r in (inputs.traceability.rows if inputs.traceability else [])
        ],
        "approvals": sorted(
            (
                {
                    "artifact": inputs.artifact_titles.get(a.artifact_id, ("document", ""))[0],
                    "type": inputs.artifact_titles.get(a.artifact_id, ("", "document"))[1],
                    "version_no": a.version_no,
                    "sha256": a.content_sha256,
                    "decision": label(a.decision),
                    "by": a.approver_name,
                    "at": ts(a.created_at),
                    "comment": a.comment,
                }
                for approvals in inputs.approvals.values()
                for a in approvals.history
            ),
            key=lambda a: (a["at"] or "", a["artifact"], a["version_no"]),
        ),
        "decisions": [
            {"title": d.title, "status": d.status, "raised_by": d.raised_by_name, "final_choice": d.final_choice, "recommended": d.recommended_option}
            for d in sorted(inputs.decisions, key=lambda d: (d.created_at, d.title))
        ],
        "change_requests": [
            {
                "id": r.cr_id,
                "title": r.title,
                "status": r.status,
                "reason": r.reason,
                "change": r.change,
                "impact": r.impact,
                "affected": list(r.affected_item_ids),
                "allows_new_items": r.allows_new_items,
                "raised_by": r.raised_by_name,
                "baseline_version_no": r.baseline_version_no,
                "applied_version_no": r.applied_version_no,
                "events": [
                    {"event": e.event, "role": label(e.role), "by": e.actor_name, "at": ts(e.created_at), "comment": e.comment}
                    for e in r.events
                ],
            }
            for r in sorted(inputs.change_requests, key=lambda r: r.cr_id)
        ],
        "agent_runs": [
            {
                "task": r.task_title,
                "input": f"{r.input_title} v{r.input_version_no}",
                "status": r.status,
                "model": r.model or "none",
                "cost_usd": f"{r.cost_usd:.2f}",
                "prompt_version": r.prompt_version,
                "error": r.error_message,
                "findings": len(r.findings),
                "requested_by": r.requested_by_name,
                "at": ts(r.created_at),
            }
            for r in sorted(inputs.runs, key=lambda r: r.created_at)
        ],
        "total_cost_usd": f"{sum((r.cost_usd for r in inputs.runs), start=0):.2f}" if inputs.runs else "0.00",
        "incidents": [
            {
                "id": i.incident_id,
                "title": i.title,
                "category": label(i.category),
                "severity": i.severity,
                "status": i.status,
                "occurrences": i.occurrences,
                "opened_at": ts(i.opened_at),
                "facts": {k: i.evidence.get(k) for k in ("error_code", "error_message", "attempts", "workflow_task_state", "input")},
                "rca": (
                    {
                        "cause": i.rca.cause,
                        "certainty": i.rca.cause_certainty,
                        "contributing_factors": i.rca.contributing_factors,
                        "containment": i.rca.containment,
                        "corrective_action": i.rca.corrective_action,
                        "owner": i.rca.action_owner_name,
                        "target_date": i.rca.target_date.isoformat(),
                        "verification_criteria": i.rca.verification_criteria,
                        "resolved_by": i.rca.resolved_by_name,
                    }
                    if i.rca
                    else None
                ),
                "closed_by": i.closed_by_name,
                "verification_evidence": i.verification_evidence,
            }
            for i in sorted(inputs.incidents, key=lambda i: i.incident_id)
        ],
        "defects": "Not applicable until Phase 10 (testing).",
        "exceptions": {
            "set_flags": [f"{f.check}: {f.message}" for f in (view.set_flags if view else [])],
            "flagged_items": sum(1 for i in items if i.quality_flags),
            "open_questions": [i.item_id for i in items if i.kind == "open_question"],
        },
    }


BUILDERS = {"requirements_summary": summary_data, "requirements_detailed": detailed_data}
