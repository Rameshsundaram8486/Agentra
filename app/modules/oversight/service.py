"""Business rules for incidents; the only entry point for other modules.

A failed or blocked agent run opens an incident when the configured rules say so, in the same transaction
that records the failure, with the evidence captured at that moment. A repeat failure of the same kind on
the same agent task, while an earlier incident is not yet closed, is recorded on that incident instead.
Only people resolve (with a root-cause analysis that labels how certain the cause is) and close (with
verification evidence, and not the person who resolved it). Status is derived from the events.
Detecting stalled work and notifying the Project Owner agent arrive with that agent (Increment 9).
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.audit.service import AuditService
from app.modules.decisions.authority import require_human
from app.modules.errors import InvalidTransitionError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.identity.service import SYSTEM_ACTOR, Actor, IdentityService
from app.modules.oversight import repository
from app.modules.oversight.models import Incident, IncidentEvent
from app.modules.oversight.rules import IncidentRules
from app.modules.oversight.schemas import IncidentClose, IncidentEventView, IncidentStatus, IncidentView, RcaCreate, RcaView

__all__ = ["IncidentClose", "IncidentView", "OversightService", "RcaCreate"]


def _status(events: list[IncidentEvent]) -> IncidentStatus:
    status: IncidentStatus = "open"
    for event in events:
        if event.event == "closed":
            return "closed"
        status = "resolved" if event.event == "resolved" else "open"  # a recurrence reopens a resolved incident
    return status


class OversightService:
    def __init__(self, session: Session, clock: Clock, audit: AuditService, identity: IdentityService, rules: IncidentRules) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._rules = rules

    # Opening (called by the executions module when a run fails or is blocked) ------------------

    def record_run_failure(
        self,
        *,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        task_id: uuid.UUID | None,
        agent_key: str,
        task_key: str,
        error_code: str | None,
        title: str,
        evidence: dict[str, Any],
    ) -> uuid.UUID | None:
        """Returns the incident the failure was recorded on, or None if the rules do not open one."""
        rule = self._rules.for_code(error_code)
        if not rule.open:
            return None
        group_key = f"{agent_key}.{task_key}"
        category = error_code or "unknown"
        now = self._clock.now()
        for existing in repository.incidents_like(self._session, project_id, group_key, category):
            events = repository.events_for(self._session, [existing.id])[existing.id]
            if _status(events) != "closed":
                repository.add(
                    self._session,
                    IncidentEvent(
                        incident_id=existing.id,
                        project_id=project_id,
                        event="recurrence",
                        actor_id=SYSTEM_ACTOR.id,
                        data={"run_id": str(run_id), "message": evidence.get("error_message")},
                        created_at=now,
                    ),
                )
                self._audit.record(
                    actor_id=SYSTEM_ACTOR.id,
                    action="incident.recurrence",
                    entity_type="incident",
                    entity_id=existing.id,
                    project_id=project_id,
                    after={"incident": self._label(existing), "run_id": str(run_id)},
                )
                return existing.id
        incident = Incident(
            project_id=project_id,
            number=repository.next_number(self._session, project_id),
            title=title[:300],
            category=category,
            severity=rule.severity,
            source_type="agent_run",
            source_id=run_id,
            task_id=task_id,
            task_key=group_key,
            evidence=evidence,
            opened_at=now,
        )
        repository.add(self._session, incident)
        self._audit.record(
            actor_id=SYSTEM_ACTOR.id,
            action="incident.open",
            entity_type="incident",
            entity_id=incident.id,
            project_id=project_id,
            after={"incident": self._label(incident), "category": category, "severity": rule.severity, "run_id": str(run_id)},
        )
        return incident.id

    # People ------------------------------------------------------------------------------------

    def resolve(self, actor: Actor, incident_id: uuid.UUID, data: RcaCreate) -> IncidentView:
        incident = self._load(incident_id)
        self._identity.require_project(actor, incident.project_id, "incident.manage")
        require_human(actor, "resolve an incident")
        data = RcaCreate.model_validate(data)
        if self._current_status(incident) != "open":
            raise InvalidTransitionError(f"{self._label(incident)} is not open")
        owner = next(
            (m for m in self._identity.list_members(actor, incident.project_id) if m.email == data.action_owner_email.strip().lower() and m.kind == "human"),
            None,
        )
        if owner is None:
            raise ValidationFailedError("The corrective action owner must be a person on this project")
        payload = data.model_dump(mode="json", exclude={"action_owner_email"}) | {"action_owner_id": str(owner.user_id)}
        self._add_event(incident, "resolved", actor, payload)
        return self._views([incident])[0]

    def close(self, actor: Actor, incident_id: uuid.UUID, data: IncidentClose) -> IncidentView:
        incident = self._load(incident_id)
        self._identity.require_project(actor, incident.project_id, "incident.close")
        require_human(actor, "close an incident")
        data = IncidentClose.model_validate(data)
        events = repository.events_for(self._session, [incident.id])[incident.id]
        if _status(events) != "resolved":
            raise InvalidTransitionError(f"{self._label(incident)} must be resolved, with a root-cause analysis, before it is closed")
        resolver = next(event.actor_id for event in reversed(events) if event.event == "resolved")
        if self._rules.closing.independent_verification and resolver == actor.id:
            raise PermissionDeniedError("You resolved this incident, so another person must verify and close it")
        self._add_event(incident, "closed", actor, {"verification_evidence": data.verification_evidence.strip()})
        return self._views([incident])[0]

    def list_incidents(self, actor: Actor, project_id: uuid.UUID) -> list[IncidentView]:
        self._identity.require_project(actor, project_id, "incident.view")
        return self._views(repository.incidents_for_project(self._session, project_id))

    def get_incident(self, actor: Actor, incident_id: uuid.UUID) -> IncidentView:
        incident = self._load(incident_id)
        self._identity.require_project(actor, incident.project_id, "incident.view")
        return self._views([incident])[0]

    # Helpers -------------------------------------------------------------------------------------

    @staticmethod
    def _label(incident: Incident) -> str:
        return f"INC-{incident.number:03d}"

    def _load(self, incident_id: uuid.UUID) -> Incident:
        incident = repository.get_incident(self._session, incident_id)
        if incident is None:
            raise NotFoundError("Incident not found")
        return incident

    def _current_status(self, incident: Incident) -> IncidentStatus:
        return _status(repository.events_for(self._session, [incident.id])[incident.id])

    def _add_event(self, incident: Incident, event: str, actor: Actor, data: dict[str, Any]) -> None:
        repository.add(
            self._session,
            IncidentEvent(incident_id=incident.id, project_id=incident.project_id, event=event, actor_id=actor.id, data=data, created_at=self._clock.now()),
        )
        self._audit.record(
            actor_id=actor.id,
            action=f"incident.{event}",
            entity_type="incident",
            entity_id=incident.id,
            project_id=incident.project_id,
            reason=data.get("cause") or data.get("verification_evidence"),
            after={"incident": self._label(incident), **{k: v for k, v in data.items() if k in ("cause_certainty", "target_date", "action_owner_id")}},
        )

    def _views(self, incidents: list[Incident]) -> list[IncidentView]:
        events = repository.events_for(self._session, [incident.id for incident in incidents])
        people = {e.actor_id for rows in events.values() for e in rows}
        people |= {uuid.UUID(e.data["action_owner_id"]) for rows in events.values() for e in rows if e.event == "resolved"}
        names = self._identity.display_names(people)
        views = []
        for incident in incidents:
            rows = events[incident.id]
            resolution = next((e for e in reversed(rows) if e.event == "resolved"), None)
            closing = next((e for e in rows if e.event == "closed"), None)
            rca = None
            if resolution is not None:
                data = dict(resolution.data)
                owner_id = uuid.UUID(data.pop("action_owner_id"))
                rca = RcaView(
                    **data,
                    action_owner_name=names.get(owner_id),
                    resolved_by=resolution.actor_id,
                    resolved_by_name=names.get(resolution.actor_id),
                    resolved_at=resolution.created_at,
                )
            views.append(
                IncidentView(
                    id=incident.id,
                    project_id=incident.project_id,
                    incident_id=self._label(incident),
                    title=incident.title,
                    category=incident.category,
                    severity=incident.severity,  # type: ignore[arg-type]
                    status=_status(rows),
                    source_type=incident.source_type,
                    source_id=incident.source_id,
                    task_id=incident.task_id,
                    task_key=incident.task_key,
                    evidence=incident.evidence,
                    occurrences=1 + sum(1 for e in rows if e.event == "recurrence"),
                    rca=rca,
                    closed_by_name=names.get(closing.actor_id) if closing else None,
                    verification_evidence=closing.data.get("verification_evidence") if closing else None,
                    events=[
                        IncidentEventView(event=e.event, actor_id=e.actor_id, actor_name=names.get(e.actor_id), data=e.data, created_at=e.created_at)  # type: ignore[arg-type]
                        for e in rows
                    ],
                    opened_at=incident.opened_at,
                )
            )
        return views
