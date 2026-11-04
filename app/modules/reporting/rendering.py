"""Renders report data as a standalone HTML document with Jinja2.

Every value is HTML-escaped (autoescape), so text that came from documents, people or agents cannot inject
markup. Undefined variables are errors, not blanks. The output has no scripts; the stylesheet is served by the
app. The template version (a hash of the template files) is stored with each report version.
"""

import hashlib
from functools import cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE_FILES = {"requirements_summary": "executive_summary.html.j2", "requirements_detailed": "detailed_report.html.j2"}


@cache
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(enabled_extensions=("html", "j2"), default=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


@cache
def template_version() -> str:
    digest = hashlib.sha256()
    for path in sorted(TEMPLATES_DIR.glob("*.j2")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:16]


def render(report_type: str, data: dict[str, Any], meta: dict[str, Any]) -> str:
    return _environment().get_template(TEMPLATE_FILES[report_type]).render(data=data, meta=meta)
