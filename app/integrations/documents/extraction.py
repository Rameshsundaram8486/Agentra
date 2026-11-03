"""Turns an uploaded file into text that agents can read and quote: plain text, Markdown, Word (.docx), PDF.

The extracted text is what gets stored as the document version, so agents' quotes are checked against
exactly what people can see. The original file is kept separately by its hash.

Limits guard the host process (parsing happens here, not in a sandbox): file size, the uncompressed size
and entry count of a .docx (a zip), and the page count of a PDF. Scanned PDFs without a text layer are
refused rather than silently stored empty; OCR is not supported.
"""

import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Literal

MAX_UPLOAD_BYTES = 10_000_000
MAX_DOCX_UNCOMPRESSED_BYTES = 60_000_000
MAX_DOCX_ENTRIES = 2_000
MAX_PDF_PAGES = 300
MIN_TEXT_CHARS = 20

FileType = Literal["text", "markdown", "docx", "pdf"]
_EXTENSIONS: dict[str, FileType] = {".txt": "text", ".md": "markdown", ".markdown": "markdown", ".docx": "docx", ".pdf": "pdf"}
SUPPORTED = ", ".join(sorted(_EXTENSIONS))

logging.getLogger("pypdf").setLevel(logging.ERROR)  # malformed-but-readable PDFs are common; don't flood the logs


class ExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedDocument:
    text: str  # Markdown
    file_type: FileType
    pages: int | None = None
    warnings: list[str] = field(default_factory=list)


def extract(filename: str, data: bytes) -> ExtractedDocument:
    file_type = _EXTENSIONS.get(PurePath(filename).suffix.lower())
    if file_type is None:
        raise ExtractionError(f"Unsupported file type; use one of {SUPPORTED}")
    if not data:
        raise ExtractionError("The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ExtractionError(f"The file is larger than {MAX_UPLOAD_BYTES // 1_000_000} MB")
    if file_type == "docx":
        result = _docx(data)
    elif file_type == "pdf":
        result = _pdf(data)
    else:
        result = _text(data, file_type)
    if len(result.text.strip()) < MIN_TEXT_CHARS:
        raise ExtractionError("No readable text was found in the file")
    return result


def _text(data: bytes, file_type: FileType) -> ExtractedDocument:
    if b"\x00" in data:
        raise ExtractionError("This does not look like a text file")
    warnings = []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
        warnings.append("The file was not UTF-8; it was read as Windows-1252")
    return ExtractedDocument(text=text.replace("\r\n", "\n").strip() + "\n", file_type=file_type, warnings=warnings)


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _docx(data: bytes) -> ExtractedDocument:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES or sum(entry.file_size for entry in entries) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ExtractionError("The Word file is too large once uncompressed")
        document = Document(io.BytesIO(data))
    except ExtractionError:
        raise
    except Exception as exc:  # python-docx and zipfile raise many types for damaged files
        raise ExtractionError(f"The Word file could not be read ({type(exc).__name__})") from exc

    lines: list[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = " ".join(paragraph.text.split())
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            heading = re.match(r"Heading (\d)", style)
            if style == "Title":
                lines.append(f"# {text}")
            elif heading:
                lines.append(f"{'#' * min(int(heading.group(1)) + 1, 6)} {text}")
            elif style.startswith("List"):
                lines.append(f"- {text}")
            else:
                lines.append(text)
        elif tag == "tbl":
            rows = [[_cell(cell.text) for cell in row.cells] for row in Table(child, document).rows]
            if rows:
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("|" + " --- |" * len(rows[0]))
                lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return ExtractedDocument(text="\n\n".join(lines) + "\n", file_type="docx")


def _pdf(data: bytes) -> ExtractedDocument:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    if not data.startswith(b"%PDF"):
        raise ExtractionError("This does not look like a PDF file")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("The PDF is password-protected")
        count = len(reader.pages)
        if count > MAX_PDF_PAGES:
            raise ExtractionError(f"The PDF has {count} pages; the limit is {MAX_PDF_PAGES}")
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except ExtractionError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError) as exc:
        raise ExtractionError(f"The PDF could not be read ({type(exc).__name__})") from exc

    empty = [number for number, text in enumerate(pages, start=1) if not text]
    if len(empty) == count:
        raise ExtractionError("The PDF has no text layer (a scan?); OCR is not supported, so upload a text version")
    warnings = [f"No text on page(s) {', '.join(map(str, empty))}; they may be scanned images"] if empty else []
    text = "\n\n".join(f"## Page {number}\n\n{body}" for number, body in enumerate(pages, start=1) if body)
    return ExtractedDocument(text=text + "\n", file_type="pdf", pages=count, warnings=warnings)
