"""Shared data for agent tests: a synthetic project brief and a Business Analyst output that is grounded in it."""

import copy
import json
import uuid
from typing import Any

from app.harness.runner import AgentRunner
from app.infrastructure.job_queue import ClaimedJob
from app.modules.executions.schemas import AgentRunCreate
from app.modules.workflow.service import TransitionRequest

BRIEF = """# Leave Management - project brief

**Customer:** Example Trading LLC, a trading company with about 200 employees in Dubai and Abu Dhabi.

## Problem
Leave requests are made by email and tracked in a shared Excel sheet. Managers lose requests, and HR spends
two days each month reconciling balances.

## What we want
- Employees request annual, sick and unpaid leave online.
- Line managers approve or reject requests; HR can see everything.
- Leave balances follow UAE labour law and are visible to employees.
- Monthly leave reports for HR.

## Constraints
- The company already uses Microsoft 365.
- The first version should be live within three months.
- Budget is limited and the IT team is two people.
"""


def _decision(title: str, keys: list[str], quotes: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "question": f"Which {title.lower()} should the project use?",
        "context": "Fact from the brief: the company uses Microsoft 365. Assumption: the IT team prefers low-code tools.",
        "options": [
            {
                "key": key,
                "title": key.replace("_", " ").title(),
                "description": f"Use {key.replace('_', ' ')}.",
                "pros": ["Fits the timeline"],
                "cons": ["Licensing cost to confirm"],
            }
            for key in keys
        ],
        "recommended_option": keys[0],
        "recommendation_rationale": "It reuses the Microsoft 365 tenant the company already has.",
        "assumptions": ["Microsoft 365 licences include Power Apps"],
        "risks": ["Licensing may need an upgrade"],
        "source_quotes": quotes,
    }


_OUTPUT: dict[str, Any] = {
    "brief_summary": "Example Trading LLC wants online leave requests with manager approval and HR reporting.",
    "technology_stack": _decision(
        "Technology stack",
        ["power_platform", "sharepoint_spfx", "custom_azure_app"],
        ["The company already uses Microsoft 365."],
    ),
    "delivery_approach": _decision(
        "Delivery approach",
        ["phased_mvp", "single_release"],
        ["The first version should be live within three months."],
    ),
    "clarifying_questions": [
        {
            "category": "business_rules",
            "title": "Approval chain",
            "question": "Is one manager approval enough, or do some requests also need HR approval?",
            "why_it_matters": "It sets the workflow and the roles the system needs.",
            "suggested_answers": [
                {"key": "manager_only", "title": "Line manager only", "description": "HR only views."},
                {"key": "manager_then_hr", "title": "Manager, then HR", "description": "HR confirms long leave."},
            ],
            "recommended_answer": None,
            "recommendation_rationale": "",
            "source_quotes": ["Line managers approve or reject requests; HR can see everything."],
        },
        {
            "category": "data",
            "title": "Existing balances",
            "question": "Should the current balances in the Excel sheet be imported?",
            "why_it_matters": "Employees need correct balances on day one.",
            "suggested_answers": [
                {"key": "import", "title": "Import them", "description": ""},
                {"key": "start_fresh", "title": "Start fresh", "description": "HR enters opening balances."},
            ],
            "recommended_answer": "import",
            "recommendation_rationale": "HR already reconciles balances monthly, so the sheet is the best source.",
            "source_quotes": ["tracked in a shared Excel sheet"],
        },
    ],
}


def ba_output(**changes: Any) -> dict[str, Any]:
    """A valid output; keyword changes replace top-level fields."""
    output = copy.deepcopy(_OUTPUT)
    output.update(changes)
    return output


def ba_json(**changes: Any) -> str:
    return json.dumps(ba_output(**changes))


def process(runner: AgentRunner, run_id: uuid.UUID, attempt: int = 1) -> None:
    """What the worker does for one claimed job (the queue itself is covered by test_job_queue)."""
    runner.handle(ClaimedJob(uuid.uuid4(), "agent_run", {"agent_run_id": str(run_id)}, "test", attempt))


DISCOVERY_NOTES = """# Discovery notes (synthetic)

HR lead: annual leave is 30 calendar days for staff with more than five years of service.
Line managers want an email when a request is waiting, and a reminder after two working days.
The warehouse supervisor said shift workers share one tablet in the break room.
"""

BRIEF_QUOTE = "The company already uses Microsoft 365."


def req(
    ref: str,
    kind: str,
    title: str,
    statement: str,
    *,
    label: str = "fact",
    priority: str = "must",
    criteria: list[str] | None = None,
    sources: list[dict[str, str]] | None = None,
    answers: list[dict[str, str]] | None = None,
    recommended: str | None = None,
    rationale: str = "",
    related: list[str] | None = None,
) -> dict[str, Any]:
    """One draft_requirements output item; by default a fact quoting the brief."""
    testable = kind in ("functional", "non_functional", "user_story")
    return {
        "ref": ref,
        "kind": kind,
        "title": title,
        "statement": statement,
        "label": label,
        "priority": priority if testable or kind == "business_rule" else "not_set",
        "acceptance_criteria": criteria if criteria is not None else (["A tester can submit a request and see it listed within 5 seconds"] if testable else []),
        "sources": sources or [{"ref": "DOC-1", "quote": BRIEF_QUOTE}],
        "related": related or [],
        "suggested_answers": answers or [],
        "recommended_answer": recommended,
        "recommendation_rationale": rationale,
    }


def draft_items() -> list[dict[str, Any]]:
    return [
        req("new-1", "objective", "Stop losing leave requests", "Every leave request is recorded and visible to the right manager.",
            sources=[{"ref": "DOC-1", "quote": "Managers lose requests"}]),
        req("new-2", "stakeholder", "Line managers", "Line managers approve or reject their team's leave.",
            sources=[{"ref": "DOC-1", "quote": "Line managers approve or reject requests"}]),
        req("new-3", "functional", "Request leave online", "Employees can request annual, sick and unpaid leave online.",
            sources=[{"ref": "DOC-1", "quote": "Employees request annual, sick and unpaid leave online."}], related=["new-1"]),
        req("new-4", "functional", "Platform", "The solution is built on Microsoft Power Platform.",
            sources=[{"ref": "DEC-1", "quote": ""}], related=["new-1"]),  # rests on the stack decision
        req("new-5", "functional", "Manager reminders", "Managers get a reminder after two working days.",
            sources=[{"ref": "DOC-2", "quote": "a reminder after two working days"}]),
        req("new-6", "assumption", "Licences", "Microsoft 365 licences include Power Apps.", label="assumption"),
        req("new-7", "open_question", "Import balances?", "Should current balances be imported from the Excel sheet?",
            label="open_question",
            sources=[{"ref": "DOC-1", "quote": "tracked in a shared Excel sheet"}],
            answers=[{"key": "import", "title": "Import them", "description": ""},
                     {"key": "start_fresh", "title": "Start fresh", "description": ""}],
            recommended="import", rationale="HR already reconciles the sheet monthly."),
    ]


def draft_output(items: list[dict[str, Any]] | None = None, **changes: Any) -> dict[str, Any]:
    output = {
        "summary": "An online leave request and approval system for Example Trading LLC.",
        "items": items if items is not None else draft_items(),
        "process_flow_mermaid": "flowchart TD\n  A[Employee requests leave] --> B{Manager decides}",
        "review_responses": [],
    }
    output.update(changes)
    return output


def draft_json(items: list[dict[str, Any]] | None = None, **changes: Any) -> str:
    return json.dumps(draft_output(items, **changes))


def ask(run: Any, team: Any, task_key: str, version_id: uuid.UUID, actor: Any = None, change_request_id: uuid.UUID | None = None) -> Any:
    """Asks the Business Analyst agent for a task, as the PM unless another actor is given."""
    data = AgentRunCreate(agent_key="business_analyst", task_key=task_key, artifact_version_id=version_id, change_request_id=change_request_id)
    return run(lambda s: s.executions.request_run(actor or team.pm.actor, team.project.id, data))


def phase_task(run: Any, team: Any, key: str, phase: int = 7) -> Any:
    current = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == phase)
    return next(t for t in current.tasks if t.key == key)


def move_task(run: Any, actor: Any, task: Any, to_state: str) -> Any:
    request = TransitionRequest(to_state=to_state, reason="Test step", expected_version=task.version)
    return run(lambda s: s.workflow.transition_task(actor, task.id, request))


# Scripted Solution Architect outputs (Phase 8)

def compare_output(**changes: Any) -> dict[str, Any]:
    criteria = [
        {"key": "fit", "title": "Fit to requirements", "weight": 5, "description": "Covers the leave workflow"},
        {"key": "cost", "title": "Cost", "weight": 3, "description": "Licences and build effort"},
        {"key": "skills", "title": "Team skills", "weight": 2, "description": "Two-person IT team"},
    ]

    def option(key: str, scores: tuple[int, int, int]) -> dict[str, Any]:
        return {
            "key": key, "title": key.replace("_", " ").title(), "description": f"Build on {key}.",
            "scores": [{"criterion": c["key"], "score": s, "rationale": "Reason"} for c, s in zip(criteria, scores)],
            "pros": ["Quick"], "cons": ["Licences"], "risks": ["Limits"],
        }

    output = {
        "summary": "The choice is driven by fit and cost.",
        "criteria": criteria,
        "options": [option("power_apps", (4, 4, 5)), option("custom_web_app", (5, 2, 2))],
        "recommended_option": "power_apps",
        "recommendation_rationale": "Best balance for a small team.",
        "assumptions": ["Licences include Power Apps"],
        "unverified_capabilities": ["Dataverse capacity included in current licences"],
        "sources": [{"ref": "REQ-F-001", "quote": ""}, {"ref": "DEC-1", "quote": ""}, {"ref": "DOC-1", "quote": BRIEF_QUOTE}],
    }
    output.update(changes)
    return output


def ditem(ref: str, kind: str, title: str, satisfies: list[str] | None = None, *, related: list[str] | None = None, **changes: Any) -> dict[str, Any]:
    item = {
        "ref": ref, "kind": kind, "title": title, "description": f"{title} description.", "rationale": "Because." if kind == "decision" else "",
        "label": "suggestion", "satisfies": satisfies or [], "related": related or [], "unverified_capabilities": [],
        "sources": [{"ref": (satisfies or ["REQ-F-001"])[0], "quote": ""}],
        "suggested_answers": [], "recommended_answer": None, "recommendation_rationale": "",
    }
    item.update(changes)
    return item


def design_items() -> list[dict[str, Any]]:
    return [
        ditem("new-1", "component", "Leave app", ["REQ-F-001", "REQ-F-002"]),
        ditem("new-2", "interface", "Reminder emails", ["REQ-F-003"], related=["new-1"]),
        ditem("new-3", "entity", "Leave request", ["REQ-F-001"], related=["new-1"]),
        ditem("new-4", "security_control", "Sign-in with Microsoft 365", ["REQ-F-001"], related=["new-1"],
              unverified_capabilities=["Conditional access is licensed"]),
        ditem("new-5", "environment", "Production tenant", [], related=["new-1"]),
        ditem("new-6", "decision", "Use Power Apps", ["REQ-F-002"], related=["new-1"]),
    ]


def design_json(items: list[dict[str, Any]] | None = None, **changes: Any) -> str:
    output = {
        "summary": "A Power Apps leave app on the existing tenant.",
        "component_diagram": "flowchart LR\n  U[Employee] --> A[Leave app]",
        "data_flow_diagram": "flowchart LR\n  A[Leave app] --> M[Manager email]",
        "items": items if items is not None else design_items(),
        "exceptions": [],
        "review_responses": [],
    }
    output.update(changes)
    return json.dumps(output)


# Scripted Security Reviewer and Developer outputs (Phase 8 reviews). The design from design_items() gets the IDs
# CMP-001, API-001, ENT-001, SEC-001, ENV-001 and ADR-001.

DESIGN_IDS = ["CMP-001", "API-001", "ENT-001", "SEC-001", "ENV-001", "ADR-001"]
CHECK_IDS = [f"SC-{n:02d}" for n in range(1, 11)]


def sfinding(check: str, verdict: str = "addressed", severity: str | None = None, items: list[str] | None = None, **changes: Any) -> dict[str, Any]:
    finding = {
        "check": check, "verdict": verdict, "severity": severity,
        "assessment": f"{check}: the design handles this in {', '.join(items or ['SEC-001'])}." if verdict == "addressed" else f"{check}: not handled by the design.",
        "recommendation": "Add a security control for it." if verdict == "gap" else "",
        "design_items": (items or ["SEC-001"]) if verdict == "addressed" else [],
        "requirements": [], "unverified_capabilities": [],
    }
    finding.update(changes)
    return finding


def security_findings(**gaps: str) -> list[dict[str, Any]]:
    """Every check addressed, except the checks given as gaps: security_findings(SC_03="high")."""
    gaps = {key.replace("_", "-"): severity for key, severity in gaps.items()}
    return [sfinding(c, "gap", gaps[c]) if c in gaps else sfinding(c) for c in CHECK_IDS]


def security_json(findings: list[dict[str, Any]] | None = None, **changes: Any) -> str:
    output = {"summary": "Sign-in and access are handled by Microsoft 365; data retention needs detail.", "findings": findings if findings is not None else security_findings(),
              "review_responses": []}
    output.update(changes)
    return json.dumps(output)


def ffinding(item: str, verdict: str = "feasible", complexity: str = "M", **changes: Any) -> dict[str, Any]:
    finding = {
        "design_item": item, "verdict": verdict, "complexity": complexity, "assessment": f"{item} can be built with Power Apps.",
        "recommendation": "" if verdict == "feasible" else "Run a one-day spike first.", "related_items": [], "unverified_capabilities": [],
    }
    finding.update(changes)
    return finding


def feasibility_json(findings: list[dict[str, Any]] | None = None, **changes: Any) -> str:
    output = {"summary": "Buildable by the two-person team in about six weeks.", "findings": findings if findings is not None else [ffinding(i) for i in DESIGN_IDS],
              "review_responses": []}
    output.update(changes)
    return json.dumps(output)


def kept_design_items() -> list[dict[str, Any]]:
    """design_items() as a redraft that keeps every existing ID."""
    items = design_items()
    ids = dict(zip([item["ref"] for item in items], DESIGN_IDS))
    for item in items:
        item["ref"], item["related"] = ids[item["ref"]], [ids[ref] for ref in item["related"]]
    return items


# Scripted Developer backlog (Phase 8). Plans the design from design_items(): every buildable item is implemented.

def witem(ref: str, design_items: list[str], wave: int = 1, depends_on: list[str] | None = None, **changes: Any) -> dict[str, Any]:
    item = {
        "ref": ref, "epic": "new-e1", "title": f"Build {', '.join(design_items)}", "description": f"Implement {', '.join(design_items)}.",
        "work_type": "build", "design_items": design_items, "requirements": [], "acceptance_criteria": [], "estimate": "M",
        "depends_on": depends_on or [], "wave": wave,
    }
    item.update(changes)
    return item


def backlog_items() -> list[dict[str, Any]]:
    return [
        witem("new-1", ["ENV-001"], work_type="deploy", estimate="S"),
        witem("new-2", ["SEC-001"], work_type="configure"),
        witem("new-3", ["ENT-001"], depends_on=["new-1"]),
        witem("new-4", ["CMP-001"], wave=2, depends_on=["new-3", "new-2"], acceptance_criteria=["REQ-F-001.AC1"]),
        witem("new-5", ["API-001"], wave=2, depends_on=["new-4"], work_type="integrate", requirements=["REQ-F-002"]),
    ]


def backlog_json(items: list[dict[str, Any]] | None = None, epics: list[dict[str, Any]] | None = None, **changes: Any) -> str:
    output = {
        "summary": "Foundations first, then the app and its reminders.",
        "epics": epics if epics is not None else [{"ref": "new-e1", "title": "Leave app", "description": "The Power Apps leave app."}],
        "items": items if items is not None else backlog_items(),
        "review_responses": [],
    }
    output.update(changes)
    return json.dumps(output)
