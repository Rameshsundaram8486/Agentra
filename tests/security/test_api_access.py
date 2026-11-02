"""Backend enforcement: every rule here must hold no matter what the UI shows or hides."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.clock import FixedClock
from app.main import create_app
from tests.support import Team, TestUser

ClientFor = Callable[..., TestClient]


def _phase_7(client: TestClient, team: Team) -> dict:
    phases = client.get(f"/api/projects/{team.project.id}/phases").json()
    return next(p for p in phases if p["phase"] == 7)


def _transition(client: TestClient, phase: dict, to_state: str, version: int | None = None) -> object:
    body = {"to_state": to_state, "reason": "api test", "expected_version": version or phase["version"]}
    return client.post(f"/api/phase-runs/{phase['id']}/transitions", json=body)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/auth/me"),
        ("get", "/api/projects"),
        ("post", "/api/projects"),
        ("get", "/api/audit/verify"),
    ],
)
def test_every_api_route_requires_a_session(client_for: ClientFor, method: str, path: str) -> None:
    response = getattr(client_for(), method)(path)

    assert response.status_code == 401
    assert response.json()["error"] == "authentication_required"


def test_wrong_password_unknown_email_and_agent_accounts_get_the_same_answer(
    client_for: ClientFor, make_user: Callable[..., TestUser]
) -> None:
    person, agent = make_user(), make_user("agent")
    client = client_for()

    answers = [
        client.post("/api/auth/login", json={"email": person.email, "password": "not-the-password"}),
        client.post("/api/auth/login", json={"email": "nobody@example.test", "password": "whatever-123456"}),
        client.post("/api/auth/login", json={"email": agent.email, "password": "whatever-123456"}),
    ]

    assert {(a.status_code, a.json()["message"]) for a in answers} == {(401, "Invalid email or password")}


def test_session_cookie_is_httponly_and_samesite_strict(client_for: ClientFor, make_user: Callable[..., TestUser]) -> None:
    user = make_user()

    response = client_for().post("/api/auth/login", json={"email": user.email, "password": user.password})

    cookie = response.headers["set-cookie"].lower()
    assert "agentra_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie


def test_session_cookie_is_secure_in_production(test_settings, clock: FixedClock, policies, make_user: Callable[..., TestUser]) -> None:
    user = make_user()
    production = test_settings.model_copy(update={"agentra_env": "production"})

    with TestClient(create_app(production, clock=clock, policies=policies)) as client:
        response = client.post("/api/auth/login", json={"email": user.email, "password": user.password})

    assert "secure" in response.headers["set-cookie"].lower()


def test_logout_revokes_the_session_on_the_server(client_for: ClientFor, make_user: Callable[..., TestUser]) -> None:
    client = client_for(make_user())
    token = client.cookies["agentra_session"]

    assert client.post("/api/auth/logout").status_code == 204

    replay = client_for()
    replay.cookies.set("agentra_session", token)
    assert replay.get("/api/auth/me").status_code == 401


def test_expired_session_is_rejected(client_for: ClientFor, make_user: Callable[..., TestUser], clock: FixedClock) -> None:
    client = client_for(make_user())
    assert client.get("/api/auth/me").status_code == 200

    clock.advance(hours=12, seconds=1)

    assert client.get("/api/auth/me").status_code == 401


def test_forged_session_token_is_rejected(client_for: ClientFor) -> None:
    client = client_for()
    client.cookies.set("agentra_session", "forged-token-value")

    assert client.get("/api/auth/me").status_code == 401


def test_outsider_gets_not_found_for_everything_in_a_project(
    client_for: ClientFor, team: Team, make_user: Callable[..., TestUser]
) -> None:
    owner, outsider = client_for(team.owner), client_for(make_user())
    phase = _phase_7(owner, team)
    pid = team.project.id

    responses = [
        outsider.get(f"/api/projects/{pid}"),
        outsider.get(f"/api/projects/{pid}/phases"),
        outsider.get(f"/api/projects/{pid}/members"),
        outsider.get(f"/api/projects/{pid}/audit"),
        outsider.get(f"/api/phase-runs/{phase['id']}/history"),
        _transition(outsider, phase, "ready"),
    ]

    assert [r.status_code for r in responses] == [404] * len(responses)
    assert pid.hex not in outsider.get("/api/projects").text.replace("-", "")


def test_non_admin_cannot_create_projects_or_verify_the_audit_chain(
    client_for: ClientFor, team: Team
) -> None:
    pm = client_for(team.pm)

    create = pm.post("/api/projects", json={"code": "NOPE-1", "name": "x", "customer_name": "y"})

    assert create.status_code == 403
    assert pm.get("/api/audit/verify").status_code == 403


def test_reviewer_cannot_add_members(client_for: ClientFor, team: Team) -> None:
    reviewer = client_for(team.reviewer)

    add = reviewer.post(
        f"/api/projects/{team.project.id}/members", json={"email": team.pm.email, "role": "reviewer"}
    )

    assert add.status_code == 403
    assert add.json()["error"] == "permission_denied"


def test_workflow_rules_are_enforced_over_http(client_for: ClientFor, team: Team) -> None:
    owner, reviewer = client_for(team.owner), client_for(team.reviewer)
    phase = _phase_7(owner, team)

    wrong_role = _transition(reviewer, phase, "ready")
    not_allowed = _transition(owner, phase, "completed")
    entry_gate = _transition(owner, next(p for p in owner.get(f"/api/projects/{team.project.id}/phases").json() if p["phase"] == 8), "ready")
    ok = _transition(owner, phase, "ready")
    stale = _transition(owner, phase, "cancelled", version=1)

    assert (wrong_role.status_code, wrong_role.json()["error"]) == (403, "permission_denied")
    assert (not_allowed.status_code, not_allowed.json()["error"]) == (409, "invalid_transition")
    assert (entry_gate.status_code, entry_gate.json()["error"]) == (409, "invalid_transition")
    assert ok.status_code == 200 and ok.json()["version"] == 2
    assert (stale.status_code, stale.json()["error"]) == (409, "conflict")


def test_invalid_request_bodies_are_rejected(client_for: ClientFor, team: Team) -> None:
    owner = client_for(team.owner)
    phase = _phase_7(owner, team)

    response = owner.post(
        f"/api/phase-runs/{phase['id']}/transitions", json={"to_state": "ready", "reason": "", "expected_version": 0}
    )

    assert response.status_code == 422


def test_security_headers(client_for: ClientFor, team: Team) -> None:
    client = client_for(team.owner)

    page = client.get("/app/control-center/login.html")
    api = client.get("/api/projects")

    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    for response in (page, api):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
    assert api.headers["cache-control"] == "no-store"
