"""Sandbox provider interface: build and test one commit of a project repository inside a disposable VM.

Agentra never runs project code on its own host (ADR 0003). A provider receives the repository and the commit,
runs the change set's test command inside a VM and reports what happened. The real VM providers (Windows Server
on Hyper-V locally, Azure in production) arrive with Increment 5b. Until then the only provider is
UnavailableSandbox, which refuses every run, so nothing is ever reported as built or tested when it was not.
A scripted provider for tests lives in the test suite, never in the application.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


class SandboxUnavailable(Exception):
    """No sandbox can run this now. The run is recorded as not run, never as passed or failed."""


@dataclass(frozen=True)
class SandboxRequest:
    project_id: uuid.UUID
    repository: Path  # the project's bare git repository; the provider copies the commit into the VM
    commit: str
    command: str
    timeout_seconds: int


@dataclass(frozen=True)
class SandboxResult:
    status: Literal["passed", "failed"]  # passed: the command exited with code 0
    exit_code: int
    output: str  # combined stdout and stderr as the VM reported it
    duration_ms: int
    provider: str
    image: str  # the VM image and version the command ran in


class SandboxProvider(Protocol):
    name: str

    def run_checks(self, request: SandboxRequest) -> SandboxResult: ...


class UnavailableSandbox:
    """The provider until sandbox VMs exist: every run ends as not run."""

    name = "none"

    def run_checks(self, request: SandboxRequest) -> SandboxResult:
        raise SandboxUnavailable("Sandbox VMs are not set up yet (they arrive with Increment 5b); nothing was built or tested")
