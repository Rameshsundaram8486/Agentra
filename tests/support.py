"""Helpers shared by tests (importable as tests.support)."""

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass

from alembic.config import Config

from app.composition import Policies
from app.harness.sandbox.provider import SandboxRequest, SandboxResult, SandboxUnavailable
from app.infrastructure.settings import ROOT_DIR
from app.modules.identity.service import Actor
from app.modules.projects.service import ProjectView
from app.modules.workflow.definitions import TaskDefinition, WorkflowCatalog

DEFAULT_PASSWORD = "correct-horse-battery-staple"


def alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def with_phase_tasks(policies: Policies, phase: int, tasks: Iterable[TaskDefinition]) -> Policies:
    """The real workflow config, with tasks added to one phase (real phase files define tasks in later increments)."""
    catalog = policies.catalog
    definition = catalog.phase(phase).model_copy(update={"tasks": tuple(tasks)})
    updated = WorkflowCatalog(lifecycles=catalog.lifecycles, phases={**catalog.phases, phase: definition})
    return dataclasses.replace(policies, catalog=updated)


class ScriptedSandbox:
    """A sandbox provider for tests only: returns scripted results in order, and with nothing scripted behaves like
    having no sandbox at all (the run is recorded as not run). Never part of the application."""

    name = "scripted"

    def __init__(self) -> None:
        self.results: list[SandboxResult | Exception] = []
        self.requests: list[SandboxRequest] = []

    def passes(self, output: str = "3 passed in 0.4s") -> None:
        self.results.append(SandboxResult("passed", 0, output, 1200, self.name, "test-image@1"))

    def fails(self, exit_code: int = 1, output: str = "1 failed, 2 passed") -> None:
        self.results.append(SandboxResult("failed", exit_code, output, 1300, self.name, "test-image@1"))

    def run_checks(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        if not self.results:
            raise SandboxUnavailable("No sandbox VM in this test")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@dataclass(frozen=True)
class TestUser:
    __test__ = False  # not a pytest test class

    actor: Actor
    email: str
    password: str | None


@dataclass(frozen=True)
class Team:
    project: ProjectView
    owner: TestUser
    pm: TestUser
    reviewer: TestUser
    agent: TestUser


def make_docx(title: str, *paragraphs: str, table: list[list[str]] | None = None) -> bytes:
    """A small Word document: a title, paragraphs and optionally a table."""
    import io

    from docx import Document

    document = Document()
    document.add_heading(title, level=0)
    document.add_heading("Details", level=1)
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.add_paragraph("First list point", style="List Bullet")
    if table:
        grid = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                grid.cell(r, c).text = value
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(*pages: str) -> bytes:
    """A minimal PDF with one text line per page; an empty string gives a page with no text (like a scan)."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids = []
    for text in pages:
        page_no, stream_no = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_no} 0 R")
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET" if text else ""
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {stream_no} 0 R /Resources << /Font << /F1 FONT 0 R >> >> >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    font_no = len(objects) + 1
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    objects = [obj.replace("FONT", str(font_no)) for obj in objects]

    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out
