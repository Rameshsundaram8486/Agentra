"""Shared data for agent tests: a synthetic project brief and a Business Analyst output that is grounded in it."""

import copy
import json
from typing import Any

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
