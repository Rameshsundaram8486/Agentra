"""Shared data for agent tests: a synthetic project brief and a Business Analyst output that is grounded in it."""

import copy
import json
import uuid
from typing import Any

from app.harness.runner import AgentRunner
from app.infrastructure.job_queue import ClaimedJob

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
            sources=[{"ref": "DOC-1", "quote": "Employees request annual, sick and unpaid leave online."}]),
        req("new-4", "functional", "Platform", "The solution is built on Microsoft Power Platform.",
            sources=[{"ref": "DEC-1", "quote": ""}]),  # rests on the stack decision
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
    }
    output.update(changes)
    return output


def draft_json(items: list[dict[str, Any]] | None = None, **changes: Any) -> str:
    return json.dumps(draft_output(items, **changes))
