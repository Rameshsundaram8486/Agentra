"""Who may start an agent run (a paid model call) and who may see runs, through the HTTP API."""

from collections.abc import Callable
from typing import Any

from tests.support import Team


def _brief_title(client: Any, brief: Any) -> str:
    return client.get(f"/api/artifacts/{brief.artifact_id}").json()["artifact"]["title"]


def _body(version_id: Any) -> dict[str, str]:
    return {"agent_key": "business_analyst", "task_key": "clarify_brief", "artifact_version_id": str(version_id)}


def test_project_manager_starts_a_run_and_asking_again_returns_it(
    ba_team: Team, make_brief: Callable[..., Any], client_for: Callable[..., Any]
) -> None:
    brief = make_brief(ba_team)
    client = client_for(ba_team.pm)
    url = f"/api/projects/{ba_team.project.id}/agent-runs"

    first = client.post(url, json=_body(brief.id))
    second = client.post(url, json=_body(brief.id))

    assert first.status_code == 202, first.text
    assert second.status_code == 200
    assert first.json()["created"] is True and second.json()["created"] is False
    run = first.json()["run"]
    assert run["status"] == "queued" and run["agent_name"] == "Business Analyst Agent"
    assert (run["input_title"], run["input_version_no"]) == (_brief_title(client, brief), 1)
    assert client.get(url).json()[0]["id"] == run["id"]
    assert client.get(f"/api/agent-runs/{run['id']}").json()["model_calls"] == []


def test_reviewers_can_see_runs_but_not_start_them(ba_team: Team, make_brief: Callable[..., Any], client_for: Callable[..., Any]) -> None:
    brief = make_brief(ba_team)
    url = f"/api/projects/{ba_team.project.id}/agent-runs"
    client_for(ba_team.pm).post(url, json=_body(brief.id))
    reviewer = client_for(ba_team.reviewer)

    assert reviewer.post(url, json=_body(brief.id)).status_code == 403
    assert reviewer.get(url).status_code == 200


def test_customer_approvers_cannot_start_or_view_runs(
    ba_team: Team, make_brief: Callable[..., Any], make_user: Callable[..., Any], add_member: Callable[..., None], client_for: Callable[..., Any]
) -> None:
    customer = make_user(name="Customer")
    add_member(ba_team.owner, ba_team.project.id, customer, "customer_approver")
    brief = make_brief(ba_team)
    url = f"/api/projects/{ba_team.project.id}/agent-runs"
    client = client_for(customer)

    assert client.post(url, json=_body(brief.id)).status_code == 403
    assert client.get(url).status_code == 403


def test_outsiders_cannot_learn_that_the_project_or_run_exists(
    ba_team: Team, make_brief: Callable[..., Any], make_user: Callable[..., Any], client_for: Callable[..., Any]
) -> None:
    brief = make_brief(ba_team)
    created = client_for(ba_team.pm).post(f"/api/projects/{ba_team.project.id}/agent-runs", json=_body(brief.id)).json()["run"]
    outsider = client_for(make_user(name="Outsider"))

    assert outsider.post(f"/api/projects/{ba_team.project.id}/agent-runs", json=_body(brief.id)).status_code == 404
    assert outsider.get(f"/api/projects/{ba_team.project.id}/agent-runs").status_code == 404
    assert outsider.get(f"/api/agent-runs/{created['id']}").status_code == 404
    assert client_for().get(f"/api/agent-runs/{created['id']}").status_code == 401


def test_a_document_from_another_project_cannot_be_used(
    ba_team: Team, make_team: Callable[..., Team], make_brief: Callable[..., Any], client_for: Callable[..., Any]
) -> None:
    other_brief = make_brief(make_team())

    response = client_for(ba_team.pm).post(f"/api/projects/{ba_team.project.id}/agent-runs", json=_body(other_brief.id))

    assert response.status_code == 404
