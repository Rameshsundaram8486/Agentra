import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.support import Team, TestUser

ClientFor = Callable[..., TestClient]


def _new_code() -> str:
    return f"API-{uuid.uuid4().hex[:8].upper()}"


def test_admin_creates_a_project_and_becomes_its_owner(client_for: ClientFor, make_user: Callable[..., TestUser]) -> None:
    founder = make_user(admin=True, name="Founder")
    client = client_for(founder)

    created = client.post(
        "/api/projects", json={"code": _new_code(), "name": "Intranet", "customer_name": "Example Co", "description": "Synthetic"}
    )
    project_id = created.json()["id"]
    detail = client.get(f"/api/projects/{project_id}").json()
    members = client.get(f"/api/projects/{project_id}/members").json()
    phases = client.get(f"/api/projects/{project_id}/phases").json()

    assert created.status_code == 201
    assert detail["my_roles"] == ["owner"]
    assert "project.manage_members" in detail["my_permissions"]
    assert [(m["display_name"], m["role"]) for m in members] == [("Founder", "owner")]
    assert [(p["phase"], p["state"], p["available_transitions"]) for p in phases] == [
        (7, "not_started", ["ready", "cancelled"]),
        (8, "not_started", ["ready", "cancelled"]),
        (9, "not_started", ["ready", "cancelled"]),
        (10, "not_started", ["ready", "cancelled"]),
        (11, "not_started", ["ready", "cancelled"]),
    ]


def test_project_codes_are_validated_and_unique(client_for: ClientFor, make_user: Callable[..., TestUser]) -> None:
    client = client_for(make_user(admin=True))
    code = _new_code()

    first = client.post("/api/projects", json={"code": code, "name": "A", "customer_name": "B"})
    duplicate = client.post("/api/projects", json={"code": code, "name": "A", "customer_name": "B"})
    lowercase = client.post("/api/projects", json={"code": "lower-case", "name": "A", "customer_name": "B"})

    assert first.status_code == 201
    assert (duplicate.status_code, duplicate.json()["error"]) == (409, "conflict")
    assert lowercase.status_code == 422


def test_owner_manages_members_by_email(client_for: ClientFor, team: Team, make_user: Callable[..., TestUser]) -> None:
    owner = client_for(team.owner)
    newcomer = make_user(name="New Reviewer")
    url = f"/api/projects/{team.project.id}/members"

    added = owner.post(url, json={"email": newcomer.email, "role": "reviewer"})
    again = owner.post(url, json={"email": newcomer.email, "role": "reviewer"})
    unknown = owner.post(url, json={"email": "ghost@example.test", "role": "reviewer"})
    bad_role = owner.post(url, json={"email": newcomer.email, "role": "superuser"})

    assert added.status_code == 201 and added.json()["role"] == "reviewer"
    assert again.status_code == 409
    assert unknown.status_code == 404
    assert bad_role.status_code == 422
    assert ("New Reviewer", "reviewer") in {(m["display_name"], m["role"]) for m in owner.get(url).json()}


def test_members_see_only_their_projects_and_admins_see_all(
    client_for: ClientFor, make_team: Callable[..., Team], make_user: Callable[..., TestUser]
) -> None:
    first, second = make_team(), make_team()
    admin = client_for(make_user(admin=True))

    pm_sees = {p["id"] for p in client_for(first.pm).get("/api/projects").json()}
    admin_sees = {p["id"] for p in admin.get("/api/projects").json()}

    assert str(first.project.id) in pm_sees and str(second.project.id) not in pm_sees
    assert {str(first.project.id), str(second.project.id)} <= admin_sees


def test_transition_appears_in_history_and_audit_with_names(client_for: ClientFor, team: Team) -> None:
    owner = client_for(team.owner)
    phase = next(p for p in owner.get(f"/api/projects/{team.project.id}/phases").json() if p["phase"] == 7)

    moved = owner.post(
        f"/api/phase-runs/{phase['id']}/transitions",
        json={"to_state": "ready", "reason": "Brief and scope received", "expected_version": 1},
    )
    history = owner.get(f"/api/phase-runs/{phase['id']}/history").json()
    audit = owner.get(f"/api/projects/{team.project.id}/audit?limit=5").json()

    assert moved.status_code == 200
    assert [(h["from_state"], h["to_state"], h["reason"]) for h in history] == [("not_started", "ready", "Brief and scope received")]
    latest = audit[0]
    assert latest["action"] == "workflow.phase_run_transition"
    assert latest["actor_name"] == team.owner.actor.display_name
    assert latest["before"] == {"state": "not_started", "version": 1}
    assert [e["seq"] for e in audit] == sorted((e["seq"] for e in audit), reverse=True)


def test_audit_pages_with_before_seq(client_for: ClientFor, team: Team) -> None:
    owner = client_for(team.owner)
    url = f"/api/projects/{team.project.id}/audit"

    first_page = owner.get(f"{url}?limit=2").json()
    next_page = owner.get(f"{url}?limit=2&before_seq={first_page[-1]['seq']}").json()

    assert len(first_page) == 2
    assert next_page and all(e["seq"] < first_page[-1]["seq"] for e in next_page)


def test_admin_can_verify_the_audit_chain(client_for: ClientFor, team: Team) -> None:
    result = client_for(team.owner).get("/api/audit/verify").json()

    assert result["ok"] is True and result["events_checked"] > 0


def test_root_redirects_to_the_control_center_and_pages_are_served(client_for: ClientFor) -> None:
    client = client_for()

    root = client.get("/", follow_redirects=False)
    login_page = client.get("/app/control-center/login.html")
    stylesheet = client.get("/app/assets/css/base.css")

    assert root.status_code == 307 and root.headers["location"] == "/app/control-center/projects.html"
    assert login_page.status_code == 200 and "<form" in login_page.text
    assert stylesheet.status_code == 200
