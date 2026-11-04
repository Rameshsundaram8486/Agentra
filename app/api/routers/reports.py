"""Reports: generate a new version from records, list versions, and read one (metadata or the HTML document)."""

import uuid
from typing import Any

from fastapi import APIRouter, Response, status
from fastapi.responses import HTMLResponse

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.reporting.schemas import GenerateResult, ReportCreate, ReportTypeView, ReportView

router = APIRouter(prefix="/api", tags=["reports"])

# The report document has no scripts; it may be framed only by the Control Center and loads only its stylesheet.
_REPORT_CSP = "default-src 'none'; style-src 'self'; img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"


@router.get("/projects/{project_id}/report-types")
def report_types(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[ReportTypeView]:
    return services.reporting.report_types(actor, project_id)


@router.post("/projects/{project_id}/reports", status_code=status.HTTP_201_CREATED)
def generate_report(
    project_id: uuid.UUID, body: ReportCreate, response: Response, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> GenerateResult:
    """201 with a new version, or 200 with the latest version when nothing has changed since it."""
    result = services.reporting.generate(actor, project_id, body)
    uow.commit()
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/projects/{project_id}/reports")
def list_reports(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[ReportView]:
    return services.reporting.list_reports(actor, project_id)


@router.get("/reports/{report_id}")
def get_report(report_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> ReportView:
    return services.reporting.get_report(actor, report_id)


@router.get("/reports/{report_id}/data")
def report_data(report_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> dict[str, Any]:
    """The exact data the report version was rendered from."""
    return services.reporting.report_data(actor, report_id)


@router.get("/reports/{report_id}/html", response_class=HTMLResponse)
def report_html(report_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> HTMLResponse:
    return HTMLResponse(
        services.reporting.report_html(actor, report_id),
        headers={"Content-Security-Policy": _REPORT_CSP, "X-Frame-Options": "SAMEORIGIN"},
    )
