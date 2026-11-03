import io
import zipfile

import pytest

from app.integrations.documents import extraction
from app.integrations.documents.extraction import ExtractionError, extract
from tests.support import make_docx, make_pdf


def test_text_and_markdown_are_read_as_utf8_with_a_fallback() -> None:
    assert extract("notes.md", "# Notes\r\n\nLeave is approved by managers.".encode()).text == "# Notes\n\nLeave is approved by managers.\n"

    legacy = extract("notes.txt", "Caf\xe9 staff request leave on paper forms.".encode("cp1252"))
    assert "Café" in legacy.text and legacy.warnings == ["The file was not UTF-8; it was read as Windows-1252"]


def test_word_headings_lists_and_tables_become_markdown() -> None:
    data = make_docx("Discovery notes", "Managers approve leave.", table=[["Leave type", "Days"], ["Annual", "30"]])

    result = extract("notes.docx", data)

    assert result.file_type == "docx"
    assert result.text.splitlines()[0] == "# Discovery notes"
    assert "## Details" in result.text and "- First list point" in result.text
    assert "| Leave type | Days |" in result.text and "| Annual | 30 |" in result.text


def test_pdf_text_is_kept_per_page_and_blank_pages_are_reported() -> None:
    result = extract("policy.pdf", make_pdf("Annual leave is thirty days.", "", "Sick leave needs a note."))

    assert result.pages == 3
    assert "## Page 1\n\nAnnual leave is thirty days." in result.text and "## Page 3" in result.text
    assert result.warnings == ["No text on page(s) 2; they may be scanned images"]


def test_a_scanned_pdf_without_text_is_refused_rather_than_stored_empty() -> None:
    with pytest.raises(ExtractionError, match="no text layer"):
        extract("scan.pdf", make_pdf("", ""))


@pytest.mark.parametrize(
    ("filename", "data", "message"),
    [
        ("tool.exe", b"MZ...", "Unsupported file type"),
        ("notes.txt", b"", "empty"),
        ("notes.txt", b"\x00\x01binary", "does not look like a text file"),
        ("fake.pdf", b"hello, I am not a PDF at all", "does not look like a PDF"),
        ("fake.docx", b"not a zip file, just some text", "could not be read"),
        ("short.txt", b"Hi.", "No readable text"),
    ],
)
def test_bad_files_are_refused_with_a_reason(filename: str, data: bytes, message: str) -> None:
    with pytest.raises(ExtractionError, match=message):
        extract(filename, data)


def test_size_and_page_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extraction, "MAX_UPLOAD_BYTES", 100)
    with pytest.raises(ExtractionError, match="larger than"):
        extract("big.txt", b"x" * 101)
    monkeypatch.undo()

    monkeypatch.setattr(extraction, "MAX_PDF_PAGES", 2)
    with pytest.raises(ExtractionError, match="the limit is 2"):
        extract("long.pdf", make_pdf("one", "two", "three"))


def test_a_word_file_that_expands_hugely_is_refused_before_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "0" * 2_000_000)  # compresses to a few kilobytes
    monkeypatch.setattr(extraction, "MAX_DOCX_UNCOMPRESSED_BYTES", 1_000_000)

    with pytest.raises(ExtractionError, match="too large once uncompressed"):
        extract("bomb.docx", buffer.getvalue())
