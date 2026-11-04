"""Business rules for reports; the only entry point for other modules.

A report is built from records only, read through each module's service with the permissions of the person
generating it, then rendered from versioned templates. The data is hashed: if nothing changed since the
latest version of that report type (same data, same templates), that version is returned instead of a copy.
Report versions are never edited, and the rendered HTML is re-hashed whenever it is read.
Customer approvers see only report types marked customer_visible in report_visibility.yaml.
"""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.infrastructure.storage.base import ArtifactStore, ContentIntegrityError
from app.modules.artifacts.service import ArtifactsService
from app.modules.backlog.service import BACKLOG_TYPE, BacklogService
from app.modules.audit.service import AuditService
from app.modules.decisions.service import DecisionsService
from app.modules.design.service import DESIGN_TYPE, DesignService
from app.modules.design_reviews.service import REVIEW_TYPES, DesignReviewsService
from app.modules.errors import ConflictError, IntegrityFailureError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.executions.service import ExecutionsService
from app.modules.identity.service import Actor, IdentityService
from app.modules.oversight.service import OversightService
from app.modules.projects.service import ProjectsService
from app.modules.reporting import repository
from app.modules.reporting.catalog import ReportCatalog
from app.modules.reporting import design_generators, generators
from app.modules.reporting.generators import ReportInputs, data_as_of, ts
from app.modules.reporting.models import Report
from app.modules.reporting.rendering import render, template_version
from app.modules.reporting.schemas import GenerateResult, ReportCreate, ReportTypeView, ReportView
from app.modules.requirements.service import BASELINE_TYPE, RequirementsService
from app.modules.workflow.service import WorkflowService

__all__ = ["GenerateResult", "ReportCreate", "ReportView", "ReportingService"]

INPUT_TYPES = ("project_brief", "source_document")
# Documents a Phase 8 report tracks with their versions and approvals.
PHASE_8_TYPES = (DESIGN_TYPE, *(artifact_type for artifact_type, _ in REVIEW_TYPES.values()), BACKLOG_TYPE)
BUILDERS = {**generators.BUILDERS, **design_generators.BUILDERS}


def _canonical(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


class ReportingService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        store: ArtifactStore,
        catalog: ReportCatalog,
        *,
        projects: ProjectsService,
        workflow: WorkflowService,
        artifacts: ArtifactsService,
        decisions: DecisionsService,
        requirements: RequirementsService,
        executions: ExecutionsService,
        oversight: OversightService,
        design: DesignService,
        design_reviews: DesignReviewsService,
        backlog: BacklogService,
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._store = store
        self._catalog = catalog
        self._projects = projects
        self._workflow = workflow
        self._artifacts = artifacts
        self._decisions = decisions
        self._requirements = requirements
        self._executions = executions
        self._oversight = oversight
        self._design = design
        self._design_reviews = design_reviews
        self._backlog = backlog

    def report_types(self, actor: Actor, project_id: uuid.UUID) -> list[ReportTypeView]:
        self._identity.require_project(actor, project_id, "project.view")
        return [
            ReportTypeView(key=key, title=kind.title, customer_visible=kind.customer_visible)
            for key, kind in self._catalog.report_types.items()
            if self._may_view(actor, project_id, key)
        ]

    def generate(self, actor: Actor, project_id: uuid.UUID, data: ReportCreate) -> GenerateResult:
        self._identity.require_project(actor, project_id, "report.generate")
        data = ReportCreate.model_validate(data)
        kind = self._catalog.get(data.report_type)
        if kind is None:
            raise ValidationFailedError(f"Unknown report type '{data.report_type}'")
        inputs = self._inputs(actor, project_id, kind.phase)
        content = BUILDERS[data.report_type](inputs)
        data_sha256 = hashlib.sha256(_canonical(content)).hexdigest()
        templates = template_version()
        latest = repository.latest(self._session, project_id, data.report_type)
        if latest is not None and latest.data_sha256 == data_sha256 and latest.template_version == templates:
            return GenerateResult(report=self._views([latest])[0], created=False)

        version_no = (latest.version_no if latest else 0) + 1
        now = self._clock.now()
        sources = self._sources(inputs)
        meta = {
            "title": kind.title,
            "version_no": version_no,
            "generated_at": ts(now),
            "generated_by": actor.display_name,
            "data_sha256": data_sha256[:16],
            "template_version": templates,
            "sources": sources,
        }
        html = render(data.report_type, content, meta).encode("utf-8")
        digest = self._store.put(html)
        report = Report(
            project_id=project_id,
            report_type=data.report_type,
            version_no=version_no,
            title=kind.title,
            data=json.loads(_canonical(content)),
            data_sha256=data_sha256,
            template_version=templates,
            content_sha256=digest,
            size_bytes=len(html),
            sources=sources,
            data_as_of=data_as_of(inputs),
            generated_by=actor.id,
            generated_at=now,
        )
        try:
            with self._session.begin_nested():
                repository.add(self._session, report)
        except IntegrityError as exc:
            raise ConflictError("Someone generated this report at the same moment; reload the list") from exc
        self._audit.record(
            actor_id=actor.id,
            action="report.generate",
            entity_type="report",
            entity_id=report.id,
            project_id=project_id,
            after={"report_type": data.report_type, "version_no": version_no, "data_sha256": data_sha256, "content_sha256": digest},
        )
        return GenerateResult(report=self._views([report])[0], created=True)

    def list_reports(self, actor: Actor, project_id: uuid.UUID) -> list[ReportView]:
        self._identity.require_project(actor, project_id, "project.view")
        rows = [r for r in repository.reports_for_project(self._session, project_id) if self._may_view(actor, project_id, r.report_type)]
        return self._views(rows)

    def get_report(self, actor: Actor, report_id: uuid.UUID) -> ReportView:
        return self._views([self._load_visible(actor, report_id)])[0]

    def report_data(self, actor: Actor, report_id: uuid.UUID) -> dict[str, Any]:
        """The exact data a report version was rendered from (for checks and integrations)."""
        return dict(self._load_visible(actor, report_id).data)

    def report_html(self, actor: Actor, report_id: uuid.UUID) -> str:
        report = self._load_visible(actor, report_id)
        try:
            content = self._store.get(report.content_sha256)
        except (ContentIntegrityError, FileNotFoundError) as exc:
            raise IntegrityFailureError(f"The stored report v{report.version_no} is missing or was altered") from exc
        if hashlib.sha256(content).hexdigest() != report.content_sha256:
            raise IntegrityFailureError(f"The stored report v{report.version_no} was altered")
        return content.decode("utf-8")

    # Helpers ---------------------------------------------------------------------------------------

    def _may_view(self, actor: Actor, project_id: uuid.UUID, report_type: str) -> bool:
        granted = self._identity.permissions_for(actor, project_id)
        if "report.view" in granted:
            return True
        kind = self._catalog.get(report_type)
        return "report.view_customer" in granted and kind is not None and kind.customer_visible

    def _load_visible(self, actor: Actor, report_id: uuid.UUID) -> Report:
        report = repository.get_report(self._session, report_id)
        if report is None:
            raise NotFoundError("Report not found")
        self._identity.require_project(actor, report.project_id, "project.view")
        if not self._may_view(actor, report.project_id, report.report_type):
            raise PermissionDeniedError("Your role on this project does not include this report")
        return report

    def _inputs(self, actor: Actor, project_id: uuid.UUID, phase_number: int) -> ReportInputs:
        project = self._projects.get_project(actor, project_id)
        phase = next(p for p in self._workflow.list_phase_runs(actor, project_id) if p.phase == phase_number)
        details = {a.id: self._artifacts.get_artifact(actor, a.id) for a in self._artifacts.list_artifacts(actor, project_id)}
        documents = [d for d in details.values() if d.artifact_type in INPUT_TYPES]
        requirements = self._requirements.view(actor, project_id)
        baseline = details.get(requirements.artifact_id) if requirements else None
        tracked = [*documents, *([baseline] if baseline else []), *(d for d in details.values() if d.artifact_type == BASELINE_TYPE and d is not baseline)]
        phase_documents = [d for d in details.values() if d.artifact_type in PHASE_8_TYPES] if phase_number == 8 else []
        approvals = {d.id: self._decisions.artifact_approvals(actor, d.id) for d in [*tracked, *phase_documents]}
        runs = self._executions.list_runs(actor, project_id)
        authors = {v.author_id for d in [*tracked, *phase_documents] for v in d.versions}
        task_histories = {t.id: self._workflow.history(actor, "task", t.id) for t in phase.tasks}
        phase_history = self._workflow.history(actor, "phase_run", phase.id)
        actors = {row.actor_id for rows in [phase_history, *task_histories.values()] for row in rows}
        return ReportInputs(
            project=project,
            phase=phase,
            phase_history=phase_history,
            task_histories=task_histories,
            documents=documents,
            baseline=baseline,
            approvals=approvals,
            artifact_titles={d.id: (d.title, d.type_title) for d in details.values()},
            decisions=self._decisions.list_decisions(actor, project_id),
            requirements=requirements,
            traceability=self._requirements.traceability(actor, project_id),
            change_requests=self._requirements.list_change_requests(actor, project_id),
            runs=runs,
            incidents=self._oversight.list_incidents(actor, project_id),
            names=self._identity.display_names(authors | actors),
            phase_documents=phase_documents,
            design=self._design.view(actor, project_id) if phase_number == 8 else None,
            reviews=self._design_reviews.view(actor, project_id) if phase_number == 8 else None,
            backlog=self._backlog.view(actor, project_id) if phase_number == 8 else None,
        )

    @staticmethod
    def _sources(inputs: ReportInputs) -> list[str]:
        sources = [f"Workflow: phase {inputs.phase.phase} ({inputs.phase.state}, version {inputs.phase.version}) and {len(inputs.phase.tasks)} task(s)"]
        for d in inputs.documents:
            sources.append(f"{d.type_title} '{d.title}' v{d.current_version_no} (sha256 {d.current_version.content_sha256[:12]})")
        if inputs.requirements:
            r = inputs.requirements
            sources.append(f"Requirements '{r.artifact_title}' v{r.version_no}: {len(r.items)} items (version {r.version_id})")
        for d in inputs.phase_documents:
            sources.append(f"{d.type_title} '{d.title}' v{d.current_version_no} (sha256 {d.current_version.content_sha256[:12]})")
        if inputs.reviews and inputs.reviews.security and inputs.reviews.security.checklist:
            sources.append(f"Security checklist: {inputs.reviews.security.checklist}")
        sources.append(f"Decisions: {len(inputs.decisions)}")
        sources.append(f"Change requests: {len(inputs.change_requests)}")
        sources.append(f"Agent runs: {len(inputs.runs)}")
        sources.append(f"Incidents: {len(inputs.incidents)}")
        sources.append(f"Approvals: {sum(len(a.history) for a in inputs.approvals.values())}")
        return sources

    def _views(self, reports: list[Report]) -> list[ReportView]:
        names = self._identity.display_names({r.generated_by for r in reports})
        return [
            ReportView(
                id=r.id,
                project_id=r.project_id,
                report_type=r.report_type,
                title=r.title,
                version_no=r.version_no,
                customer_visible=bool((kind := self._catalog.get(r.report_type)) and kind.customer_visible),
                generated_by=r.generated_by,
                generated_by_name=names.get(r.generated_by),
                generated_at=r.generated_at,
                data_as_of=r.data_as_of,
                data_sha256=r.data_sha256,
                content_sha256=r.content_sha256,
                template_version=r.template_version,
                sources=r.sources,
            )
            for r in reports
        ]
