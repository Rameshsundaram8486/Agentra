"""Loads versioned prompts and output schemas. The recorded version is the file name plus a content hash,
so an edited prompt is visible in every agent run that used it, even if the file name stayed the same.
Line endings are normalised before hashing, so a Windows and a Linux checkout give the same version."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptFile:
    text: str
    version: str  # e.g. clarify_brief.v1@3f2a9c1b0d4e


@dataclass(frozen=True)
class SchemaFile:
    schema: dict[str, Any]
    version: str


def _version(path: Path, raw: bytes) -> str:
    normalised = raw.replace(b"\r\n", b"\n")
    return f"{path.stem}@{hashlib.sha256(normalised).hexdigest()[:12]}"


def load_prompt(path: Path) -> PromptFile:
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n").strip()
    if not text:
        raise ValueError(f"{path.name} is empty")
    return PromptFile(text=text, version=_version(path, raw))


def load_schema(path: Path) -> SchemaFile:
    raw = path.read_bytes()
    schema = json.loads(raw)
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError(f"{path.name} must be a JSON Schema for an object")
    schema = {key: value for key, value in schema.items() if key != "$comment"}  # documentation only
    return SchemaFile(schema=schema, version=_version(path, raw))
