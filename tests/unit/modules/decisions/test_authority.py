import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.composition import CONFIG_DIR, load_policies
from app.modules.decisions.authority import (
    ApprovalMatrix,
    check_can_approve,
    check_can_decide,
    load_approval_matrix,
)
from app.modules.decisions.schemas import DecisionOutcomeCreate, DecisionRequestCreate
from app.modules.errors import PermissionDeniedError
from app.modules.identity.service import Actor

MATRIX = load_approval_matrix(CONFIG_DIR / "policies" / "approval_matrix.yaml")
BASELINE = MATRIX.artifact_types["requirements_baseline"]


def _actor(kind: str = "human") -> Actor:
    return Actor(id=uuid.uuid4(), kind=kind, display_name="Someone", is_platform_admin=False)  # type: ignore[arg-type]


def test_every_mvp_phase_requires_an_approval_type_that_exists() -> None:
    policies = load_policies()

    for number, phase in policies.catalog.phases.items():
        assert phase.exit.required_approvals, f"phase {number} has no required approval"
        assert set(phase.exit.required_approvals) <= set(MATRIX.artifact_types)


def test_customer_signs_off_uat_and_nobody_else_does() -> None:
    assert MATRIX.artifact_types["uat_signoff_record"].approver_roles == {"customer_approver"}


@pytest.mark.parametrize("section", ["artifact", "decisions"])
def test_matrix_listing_agent_as_approver_or_decider_is_rejected(section: str) -> None:
    data: dict[str, Any] = {
        "version": 1,
        "artifact_types": {"doc": {"title": "Doc", "approver_roles": ["reviewer"]}},
        "decisions": {"decider_roles": ["owner"]},
        "change_requests": {"required_roles": ["owner"]},
    }
    if section == "artifact":
        data["artifact_types"]["doc"]["approver_roles"] = ["reviewer", "agent"]
    else:
        data["decisions"]["decider_roles"] = ["owner", "agent"]

    with pytest.raises(ValidationError, match="human project roles"):
        ApprovalMatrix.model_validate(data)


@pytest.mark.parametrize("roles", [["owner", "agent"], ["owner", "owner"], []])
def test_change_request_roles_must_be_distinct_human_roles(roles: list[str]) -> None:
    data: dict[str, Any] = {
        "version": 1,
        "artifact_types": {"doc": {"title": "Doc", "approver_roles": ["reviewer"]}},
        "decisions": {"decider_roles": ["owner"]},
        "change_requests": {"required_roles": roles},
    }

    with pytest.raises(ValidationError, match="distinct human project roles"):
        ApprovalMatrix.model_validate(data)


def test_both_owner_and_customer_approver_must_approve_a_change_request() -> None:
    assert MATRIX.change_requests.required_roles == ("owner", "customer_approver")
    assert MATRIX.baselines == {"requirements_baseline", "design_baseline"}


@pytest.mark.parametrize("kind", ["agent", "system"])
def test_non_humans_never_approve_or_decide_whatever_their_roles(kind: str) -> None:
    every_role = {"owner", "project_manager", "reviewer", "customer_approver", "agent"}

    with pytest.raises(PermissionDeniedError, match="Only people"):
        check_can_approve(_actor(kind), every_role, BASELINE, set())
    with pytest.raises(PermissionDeniedError, match="Only people"):
        check_can_decide(_actor(kind), every_role, MATRIX.decisions)


def test_approver_needs_a_listed_role() -> None:
    with pytest.raises(PermissionDeniedError, match="needs one of these roles"):
        check_can_approve(_actor(), {"project_manager"}, BASELINE, set())

    check_can_approve(_actor(), {"reviewer"}, BASELINE, set())


def test_author_of_any_version_cannot_approve_when_review_must_be_independent() -> None:
    author = _actor()

    with pytest.raises(PermissionDeniedError, match="independent reviewer"):
        check_can_approve(author, {"owner", "reviewer"}, BASELINE, {author.id, uuid.uuid4()})


def test_author_may_approve_when_the_type_does_not_require_independence() -> None:
    author = _actor()
    relaxed = BASELINE.model_copy(update={"independent_review": False})

    check_can_approve(author, {"reviewer"}, relaxed, {author.id})


def test_decision_request_rules() -> None:
    options = [{"key": "spo", "title": "SharePoint Online"}, {"key": "spse", "title": "Subscription Edition"}]

    with pytest.raises(ValidationError, match="one of the option keys"):
        DecisionRequestCreate(title="Platform", question="Which?", options=options, recommended_option="hybrid", recommendation_rationale="r")
    with pytest.raises(ValidationError, match="needs a rationale"):
        DecisionRequestCreate(title="Platform", question="Which?", options=options, recommended_option="spo")
    with pytest.raises(ValidationError, match="unique"):
        DecisionRequestCreate(title="Platform", question="Which?", options=options + [options[0]])
    with pytest.raises(ValidationError):
        DecisionRequestCreate(title="Platform", question="Which?", options=options[:1])


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"action": "select_option"}, "selected_option is required"),
        ({"action": "accept", "selected_option": "spo"}, "not allowed otherwise"),
        ({"action": "other"}, "custom_choice is required"),
        ({"action": "other", "custom_choice": "   "}, "custom_choice is required"),
        ({"action": "accept", "custom_choice": "Hybrid"}, "not allowed otherwise"),
        ({"action": "reject"}, "comment is required"),
        ({"action": "defer", "comment": " "}, "comment is required"),
        ({"action": "modify"}, "comment is required"),
    ],
)
def test_outcome_fields_must_match_the_action(fields: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        DecisionOutcomeCreate(**fields)


def test_valid_outcomes() -> None:
    DecisionOutcomeCreate(action="accept")
    DecisionOutcomeCreate(action="select_option", selected_option="spse")
    DecisionOutcomeCreate(action="other", custom_choice="Hybrid with SharePoint Online for new sites")
    DecisionOutcomeCreate(action="defer", comment="Waiting for the customer's licence review")


def test_design_change_requests_are_decided_by_an_owner_and_a_reviewer() -> None:
    assert MATRIX.change_requests.roles_for("design_baseline") == ("owner", "reviewer")
    assert MATRIX.change_requests.roles_for("requirements_baseline") == ("owner", "customer_approver")


@pytest.mark.parametrize(
    ("by_baseline", "message"),
    [
        ({"design_baseline": ["owner", "agent"]}, "distinct human project roles"),
        ({"project_brief": ["owner", "reviewer"]}, "not baselines"),
    ],
)
def test_per_baseline_change_request_roles_are_checked(by_baseline: dict[str, list[str]], message: str) -> None:
    data = MATRIX.model_dump()
    data["change_requests"]["by_baseline"] = by_baseline

    with pytest.raises(ValidationError, match=message):
        ApprovalMatrix.model_validate(data)
