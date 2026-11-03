from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.support import Team, TestUser

ClientFor = Callable[..., TestClient]


def _create_brd(client: TestClient, team: Team, content: str = "# BRD\n\nREQ-F-001\n") -> dict:
    response = client.post(
        f"/api/projects/{team.project.id}/artifacts",
        json={"artifact_type": "requirements_baseline", "title": "Leave app BRD", "content": content},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_full_review_cycle_over_http(client_for: ClientFor, team: Team) -> None:
    pm, reviewer = client_for(team.pm), client_for(team.reviewer)
    artifact = _create_brd(pm, team)
    v1 = artifact["current_version"]

    changes = reviewer.post(
        f"/api/artifact-versions/{v1['id']}/approvals",
        json={"decision": "changes_requested", "content_sha256": v1["content_sha256"], "comment": "Add REQ-F-002"},
    )
    v2 = pm.post(
        f"/api/artifacts/{artifact['id']}/versions",
        json={"content": "# BRD\n\nREQ-F-001\nREQ-F-002\n", "change_summary": "Added REQ-F-002", "expected_current_version": 1},
    ).json()["current_version"]
    diff = reviewer.get(f"/api/artifacts/{artifact['id']}/diff?from_version=1&to_version=2").json()
    approved = reviewer.post(
        f"/api/artifact-versions/{v2['id']}/approvals", json={"decision": "approved", "content_sha256": v2["content_sha256"]}
    )
    page = reviewer.get(f"/api/artifacts/{artifact['id']}").json()
    listing = reviewer.get(f"/api/projects/{team.project.id}/artifacts").json()

    assert changes.status_code == 201
    assert "+REQ-F-002" in diff["diff"]
    assert approved.status_code == 201
    assert page["approvals"]["current"] == {**page["approvals"]["current"], "status": "approved", "version_no": 2}
    assert [a["decision"] for a in page["approvals"]["history"]] == ["approved", "changes_requested"]
    assert [(a["title"], a["current_version_no"], a["approval_status"]) for a in listing] == [("Leave app BRD", 2, "approved")]


def test_version_content_is_returned_with_its_hash(client_for: ClientFor, team: Team) -> None:
    pm = client_for(team.pm)
    v1 = _create_brd(pm, team, content="# Exact text\n")["current_version"]

    content = pm.get(f"/api/artifact-versions/{v1['id']}/content").json()

    assert content["content"] == "# Exact text\n"
    assert content["version"]["content_sha256"] == v1["content_sha256"]


def test_approval_rules_over_http(client_for: ClientFor, team: Team) -> None:
    pm, reviewer = client_for(team.pm), client_for(team.reviewer)
    v1 = _create_brd(pm, team)["current_version"]
    url = f"/api/artifact-versions/{v1['id']}/approvals"

    wrong_hash = reviewer.post(url, json={"decision": "approved", "content_sha256": "f" * 64})
    wrong_role = pm.post(url, json={"decision": "approved", "content_sha256": v1["content_sha256"]})
    bad_decision = reviewer.post(url, json={"decision": "looks_fine", "content_sha256": v1["content_sha256"]})

    assert (wrong_hash.status_code, wrong_hash.json()["error"]) == (409, "conflict")
    assert (wrong_role.status_code, wrong_role.json()["error"]) == (403, "permission_denied")
    assert bad_decision.status_code == 422


def test_phase_completion_is_blocked_until_approved_over_http(client_for: ClientFor, team: Team, close_tasks: Callable[..., None]) -> None:
    close_tasks(team, 7)
    owner, pm, reviewer = client_for(team.owner), client_for(team.pm), client_for(team.reviewer)
    phase = next(p for p in owner.get(f"/api/projects/{team.project.id}/phases").json() if p["phase"] == 7)

    def move(client: TestClient, to_state: str) -> dict:
        nonlocal phase
        response = client.post(
            f"/api/phase-runs/{phase['id']}/transitions", json={"to_state": to_state, "reason": "step", "expected_version": phase["version"]}
        )
        if response.status_code == 200:
            phase = response.json()
        return response

    move(owner, "ready"), move(pm, "in_progress"), move(pm, "waiting_for_review")
    blocked = move(reviewer, "completed")
    v1 = _create_brd(pm, team)["current_version"]
    reviewer.post(f"/api/artifact-versions/{v1['id']}/approvals", json={"decision": "approved", "content_sha256": v1["content_sha256"]})
    completed = move(reviewer, "completed")

    assert (blocked.status_code, blocked.json()["error"]) == (409, "invalid_transition")
    assert "No requirements baseline exists yet" in blocked.json()["message"]
    assert completed.status_code == 200 and completed.json()["state"] == "completed"


def test_decision_inbox_over_http(client_for: ClientFor, team: Team) -> None:
    pm, owner = client_for(team.pm), client_for(team.owner)
    raised = pm.post(
        f"/api/projects/{team.project.id}/decisions",
        json={
            "title": "Hosting",
            "question": "Where should the app run?",
            "options": [{"key": "azure", "title": "Azure App Service"}, {"key": "onprem", "title": "On-premises IIS"}],
            "recommended_option": "azure",
            "recommendation_rationale": "Customer already uses Azure",
        },
    )
    decided = owner.post(f"/api/decisions/{raised.json()['id']}/outcomes", json={"action": "other", "custom_choice": "Azure Container Apps"})
    inbox = owner.get(f"/api/projects/{team.project.id}/decisions").json()

    assert raised.status_code == 201 and raised.json()["status"] == "open"
    assert decided.status_code == 200 and decided.json()["final_choice"] == "Azure Container Apps"
    assert inbox[0]["recommended_option"] == "azure" and inbox[0]["status"] == "decided"


def test_artifact_types_are_listed_for_signed_in_users(client_for: ClientFor, make_user: Callable[..., TestUser]) -> None:
    types = {t["key"]: t for t in client_for(make_user()).get("/api/artifact-types").json()}

    assert types["uat_signoff_record"]["approver_roles"] == ["customer_approver"]
    assert all(t["independent_review"] for t in types.values())


def test_outsiders_get_not_found_for_artifacts_and_decisions(
    client_for: ClientFor, team: Team, make_user: Callable[..., TestUser]
) -> None:
    pm, outsider = client_for(team.pm), client_for(make_user())
    artifact = _create_brd(pm, team)

    responses = [
        outsider.get(f"/api/projects/{team.project.id}/artifacts"),
        outsider.get(f"/api/artifacts/{artifact['id']}"),
        outsider.get(f"/api/artifact-versions/{artifact['current_version']['id']}/content"),
        outsider.get(f"/api/projects/{team.project.id}/decisions"),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404, 404]
