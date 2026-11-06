"""Builds the Phase 8 report data from records: the design summary (customer-visible) and the detailed design pack.
Pure and deterministic like generators.py, whose helpers it shares: no clock reads, no model calls, stable
ordering, missing information labelled. The summary shows review outcomes as counts and sign-off status; the
findings themselves are only in the internal design pack.
"""

from typing import Any

from app.modules.reporting.generators import NO_DUE_DATE, ReportInputs, _approval_of, _common, _history, _versions, label, ts

DESIGN_LIMITATIONS = [
    "Work item sizes are relative (S, M, L), not effort or date commitments.",
    "Development, testing and defects start in Phases 9 and 10; the test column of the traceability matrix is empty until then.",
    "Due dates are not tracked for decisions, reviews or approvals yet.",
]
OPTION_DECISION = "Architecture option"


def _approved(inputs: ReportInputs, artifact_id: Any, version_id: Any) -> dict[str, Any] | None:
    approval = _approval_of(inputs, artifact_id, version_id)
    if approval is None or approval.decision != "approved":
        return None
    return {"by": approval.approver_name, "at": ts(approval.created_at), "sha256": approval.content_sha256}


def _option(inputs: ReportInputs) -> dict[str, Any] | None:
    decision = next((d for d in sorted(inputs.decisions, key=lambda d: d.created_at, reverse=True) if d.title == OPTION_DECISION), None)
    if decision is None:
        return None
    options = {o.key: o.title for o in decision.options}
    return {
        "status": decision.status,
        "chosen": decision.final_choice,  # in words, as recorded with the outcome
        "recommended": decision.recommended_option and options.get(decision.recommended_option, decision.recommended_option),
        "rationale": decision.recommendation_rationale,
        "options": [o.title for o in decision.options],
    }


def _design(inputs: ReportInputs) -> dict[str, Any] | None:
    view = inputs.design
    if view is None:
        return None
    kinds: dict[str, int] = {}
    for item in view.items:
        kinds[label(item.kind)] = kinds.get(label(item.kind), 0) + 1
    return {
        "title": view.artifact_title,
        "version_no": view.version_no,
        "approval_status": view.approval_status,
        "approved": _approved(inputs, view.artifact_id, view.version_id),
        "stale_reason": view.stale_reason,
        "change_request": view.change_request,
        "requirements_version_no": view.requirements_version_no,
        "summary": view.summary,
        "item_count": len(view.items),
        "kinds": dict(sorted(kinds.items())),
        "coverage": {"confirmed": view.coverage.confirmed, "covered": view.coverage.covered, "excepted": view.coverage.excepted, "gaps": list(view.coverage.gaps)},
        "decisions": [{"id": i.item_id, "title": i.title} for i in view.items if i.kind == "decision"],
        "risks": [{"id": i.item_id, "title": i.title} for i in view.items if i.kind == "risk"],
        "open_questions": [{"id": i.item_id, "title": i.title} for i in view.items if i.kind == "open_question"],
        "unverified": sum(1 for i in view.items if i.unverified_capabilities),
    }


def _review(inputs: ReportInputs, review: Any) -> dict[str, Any] | None:
    if review is None:
        return None
    gaps = {severity: sum(1 for f in review.findings if f.verdict == "gap" and f.severity == severity) for severity in ("high", "medium", "low")}
    sizes = {size: sum(1 for f in review.findings if f.complexity == size) for size in ("S", "M", "L")}
    return {
        "title": review.artifact_title,
        "version_no": review.version_no,
        "design_version_no": review.design_version_no,
        "current": review.current,
        "approval_status": review.approval_status,
        "signed_off": _approved(inputs, review.artifact_id, review.version_id),
        "checklist": review.checklist,
        "counts": {label(k): v for k, v in sorted(review.counts.items())},
        "gaps": gaps,
        "sizes": sizes,
    }


def _backlog(inputs: ReportInputs) -> dict[str, Any] | None:
    view = inputs.backlog
    if view is None:
        return None
    return {
        "title": view.artifact_title,
        "version_no": view.version_no,
        "design_version_no": view.design_version_no,
        "approval_status": view.approval_status,
        "approved": _approved(inputs, view.artifact_id, view.version_id),
        "stale_reason": view.stale_reason,
        "epics": len(view.epics),
        "items": len(view.items),
        "estimates": dict(view.estimates),
        "waves": {str(k): v for k, v in view.waves.items()},
    }


def _next_actions(
    inputs: ReportInputs, design: dict[str, Any] | None, gate: list[str], security: dict[str, Any] | None, feasibility: dict[str, Any] | None, backlog: dict[str, Any] | None
) -> list[dict[str, str]]:
    actions = []
    for decision in sorted(inputs.decisions, key=lambda d: d.created_at):
        if decision.status == "open":
            actions.append({"action": f"Answer: {decision.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    if design is None:
        actions.append({"action": "Ask the Solution Architect to draft the design", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    elif design["stale_reason"]:
        actions.append({"action": f"Redraft the design: {design['stale_reason']}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    elif design["approval_status"] != "approved":
        # Worded from counts, not the gate messages: the summary may go to customers, and findings stay internal.
        team = "Owner or project manager"
        v = f"design v{design['version_no']}"
        if security is None or not security["current"]:
            actions.append({"action": f"Have the Security Reviewer review {v}", "owner": team, "due": NO_DUE_DATE})
        elif security["gaps"]["high"]:
            actions.append({"action": f"Close {security['gaps']['high']} high-severity security gap(s) in a redraft of the design", "owner": team, "due": NO_DUE_DATE})
        elif not security["signed_off"]:
            actions.append({"action": f"Sign off {security['title']} v{security['version_no']}", "owner": "Reviewer", "due": NO_DUE_DATE})
        if feasibility is None or not feasibility["current"]:
            actions.append({"action": f"Have the Developer review the feasibility of {v}", "owner": team, "due": NO_DUE_DATE})
        elif blocked := feasibility["counts"].get("not feasible", 0):
            actions.append({"action": f"Resolve {blocked} design item(s) rated not feasible in a redraft", "owner": team, "due": NO_DUE_DATE})
        if not gate:
            actions.append({"action": f"Approve {design['title']} v{design['version_no']}", "owner": "Reviewer or owner (not its author)", "due": NO_DUE_DATE})
    elif backlog is None:
        actions.append({"action": "Ask the Developer to plan the implementation backlog", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    elif backlog["stale_reason"]:
        actions.append({"action": f"Replan the backlog: {backlog['stale_reason']}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    elif backlog["approval_status"] != "approved":
        actions.append({"action": f"Approve {backlog['title']} v{backlog['version_no']}", "owner": "Owner, project manager or reviewer", "due": NO_DUE_DATE})
    for request in sorted(inputs.change_requests, key=lambda r: r.cr_id):
        if request.status == "open":
            missing = [label(r) for r in request.required_roles if r not in request.approved_roles]
            actions.append({"action": f"Decide {request.cr_id}: {request.title}", "owner": " and ".join(missing), "due": NO_DUE_DATE})
        elif request.status == "approved":
            actions.append({"action": f"Apply {request.cr_id}: {request.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    for task in inputs.phase.tasks:
        if task.state == "waiting_for_input":
            actions.append({"action": f"Provide input for: {task.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    for incident in sorted(inputs.incidents, key=lambda i: i.incident_id):
        if incident.status == "open":
            actions.append({"action": f"Resolve {incident.incident_id}: {incident.title}", "owner": "Owner or project manager", "due": NO_DUE_DATE})
    return actions


def _milestones(inputs: ReportInputs) -> list[dict[str, str]]:
    events = []
    for detail in inputs.phase_documents:
        for version in detail.versions:
            events.append((version.created_at, f"{detail.title} v{version.version_no}: {version.change_summary}"))
        for a in inputs.approvals[detail.id].history if detail.id in inputs.approvals else []:
            events.append((a.created_at, f"{detail.title} v{a.version_no} {label(a.decision)} by {a.approver_name or 'a reviewer'}"))
    for task in inputs.phase.tasks:
        if task.state == "completed":
            events.append((task.updated_at, f"Task completed: {task.title}"))
    events.sort(key=lambda event: (event[0], event[1]), reverse=True)
    return [{"at": ts(at), "what": what} for at, what in events[:12]]


def design_summary_data(inputs: ReportInputs) -> dict[str, Any]:
    design = _design(inputs)
    backlog = _backlog(inputs)
    gate = list(inputs.reviews.gate) if inputs.reviews else []
    security = _review(inputs, inputs.reviews.security if inputs.reviews else None)
    feasibility = _review(inputs, inputs.reviews.feasibility if inputs.reviews else None)
    return {
        **_common(inputs),
        "option": _option(inputs),
        "design": design,
        "security": security,
        "feasibility": feasibility,
        "approvable": design is not None and not design["stale_reason"] and not gate,
        "backlog": backlog,
        "decisions_waiting": [{"title": d.title} for d in sorted(inputs.decisions, key=lambda d: d.created_at) if d.status == "open"],
        "blocked_tasks": [{"title": t.title, "state": label(t.state)} for t in inputs.phase.tasks if t.state in ("blocked", "failed")],
        "incidents": [
            {"id": i.incident_id, "title": i.title, "severity": i.severity, "status": i.status}
            for i in sorted(inputs.incidents, key=lambda i: i.incident_id)
            if i.status != "closed"
        ],
        "milestones": _milestones(inputs),
        "next_actions": _next_actions(inputs, design, gate, security, feasibility, backlog),
        "limitations": DESIGN_LIMITATIONS,
    }


def _findings(review: Any) -> list[dict[str, Any]]:
    return [
        {
            "ref": f.ref,
            "title": f.title,
            "verdict": label(f.verdict),
            "severity": f.severity,
            "complexity": f.complexity,
            "assessment": f.assessment,
            "recommendation": f.recommendation,
            "design_items": list(f.design_items),
            "unverified": list(f.unverified),
        }
        for f in (review.findings if review else [])
    ]


def design_detailed_data(inputs: ReportInputs) -> dict[str, Any]:
    view = inputs.design
    backlog = inputs.backlog
    phase_agents = {"solution_architect", "security_reviewer", "developer"}
    runs = [r for r in sorted(inputs.runs, key=lambda r: r.created_at) if r.agent_key in phase_agents]
    return {
        **design_summary_data(inputs),
        "gate": list(inputs.reviews.gate) if inputs.reviews else [],
        "phase_history": _history(inputs, inputs.phase_history),
        "tasks": [
            {"title": t.title, "state": label(t.state), "history": _history(inputs, inputs.task_histories.get(t.id, []))}
            for t in inputs.phase.tasks
        ],
        "documents": [
            {"title": d.title, "type": d.type_title, "versions": _versions(inputs, d)}
            for d in sorted(inputs.phase_documents, key=lambda d: (d.artifact_type, d.title))
        ],
        "design_items": [
            {
                "id": i.item_id,
                "kind": label(i.kind),
                "title": i.title,
                "description": i.description,
                "rationale": i.rationale,
                "label": label(i.label),
                "status": i.status,
                "satisfies": list(i.satisfies),
                "related": list(i.related),
                "unverified": list(i.unverified_capabilities),
                "flags": [f"{f.check}: {f.message}" for f in i.quality_flags],
            }
            for i in (view.items if view else [])
        ],
        "coverage_rows": [
            {"id": r.requirement_id, "title": r.title, "status": r.status, "design_items": list(r.design_items), "exception": r.exception}
            for r in (view.coverage.rows if view else [])
        ],
        "design_responses": [{"finding": r.finding or "Review comment", "comment": r.comment, "response": r.response} for r in (view.review_responses if view else [])],
        "security_findings": _findings(inputs.reviews.security if inputs.reviews else None),
        "feasibility_findings": _findings(inputs.reviews.feasibility if inputs.reviews else None),
        "epics": [{"id": e.epic_id, "title": e.title, "description": e.description} for e in (backlog.epics if backlog else [])],
        "work_items": [
            {
                "id": i.item_id,
                "epic": i.epic_id,
                "title": i.title,
                "work_type": i.work_type,
                "design_items": list(i.design_items),
                "requirements": list(i.requirements),
                "acceptance": list(i.acceptance),
                "estimate": i.estimate,
                "depends_on": list(i.depends_on),
                "wave": i.wave,
            }
            for i in (backlog.items if backlog else [])
        ],
        "approvals": sorted(
            (
                {
                    "artifact": inputs.artifact_titles.get(a.artifact_id, ("document", ""))[0],
                    "version_no": a.version_no,
                    "sha256": a.content_sha256,
                    "decision": label(a.decision),
                    "by": a.approver_name,
                    "at": ts(a.created_at),
                    "comment": a.comment,
                }
                for d in inputs.phase_documents
                for a in (inputs.approvals[d.id].history if d.id in inputs.approvals else [])
            ),
            key=lambda a: (a["at"] or "", a["artifact"], a["version_no"]),
        ),
        "agent_runs": [
            {
                "task": r.task_title,
                "input": f"{r.input_title} v{r.input_version_no}",
                "status": r.status,
                "model": r.model or "none",
                "cost_usd": f"{r.cost_usd:.2f}",
                "prompt_version": r.prompt_version,
                "error": r.error_message,
                "requested_by": r.requested_by_name,
                "at": ts(r.created_at),
            }
            for r in runs
        ],
        "total_cost_usd": f"{sum((r.cost_usd for r in runs), start=0):.2f}" if runs else "0.00",
        "change_requests": [
            {
                "id": r.cr_id,
                "title": r.title,
                "status": r.status,
                "reason": r.reason,
                "change": r.change,
                "impact": r.impact,
                "affected": list(r.affected_item_ids),
                "impacted_requirements": list(r.impacted_requirements),
                "impacted_work_items": list(r.impacted_work_items),
                "raised_by": r.raised_by_name,
                "design_version_no": r.baseline_version_no,
                "applied_version_no": r.applied_version_no,
                "events": [{"event": e.event, "role": label(e.role), "by": e.actor_name, "at": ts(e.created_at), "comment": e.comment} for e in r.events],
            }
            for r in sorted(inputs.change_requests, key=lambda r: r.cr_id)
        ],
    }


BUILDERS = {"design_summary": design_summary_data, "design_detailed": design_detailed_data}
