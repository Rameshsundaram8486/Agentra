"""The project git repositories Agentra keeps on its host: one bare repository per project, main as its default branch.

Agentra only stores and combines code here; it never runs it (that happens in sandbox VMs, ADR 0003). So every
command is git plumbing on a bare repository: no checkout, no working tree files, no hooks (core.hooksPath points
to an empty folder), no clean/smudge filters or external diff programs, and neither the system's nor the user's
git configuration. Commits are built in a throwaway index; main moves only by compare-and-swap, so two merges
racing cannot lose one another's work.
"""

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

MAIN = "main"
_ZERO = "0" * 40


class GitError(Exception):
    """A git command failed. The message never contains file contents."""


@dataclass(frozen=True)
class Signature:
    name: str
    email: str
    when: datetime


@dataclass(frozen=True)
class FileChange:
    path: str
    action: Literal["add", "modify", "delete"]
    content: str | None = None  # None for a delete


@dataclass(frozen=True)
class RepoFile:
    path: str
    size: int


@dataclass(frozen=True)
class MergeOutcome:
    status: Literal["merged", "already_merged", "conflict"]
    commit: str | None  # main after the merge
    conflicts: tuple[str, ...] = ()


def safe_path(path: str) -> bool:
    """A relative POSIX path inside the repository, outside .git."""
    if not path or "\\" in path or "\x00" in path or path.startswith("/") or path != path.strip():
        return False
    parts = path.split("/")  # literally: a//b and ./a are refused, not normalised
    return all(p not in ("", ".", "..") for p in parts) and parts[0].lower() != ".git" and ":" not in parts[0]


class GitRepositories:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._no_hooks = root / ".no-hooks"

    def path(self, project_id: uuid.UUID) -> Path:
        return self._root / f"{uuid.UUID(str(project_id))}.git"

    def exists(self, project_id: uuid.UUID) -> bool:
        return (self.path(project_id) / "HEAD").is_file()

    # Writes ---------------------------------------------------------------------------------------

    def ensure(self, project_id: uuid.UUID, readme: str, author: Signature) -> str:
        """Creates the repository with a first commit on main if it does not exist yet. Returns main's head."""
        path = self.path(project_id)
        self._no_hooks.mkdir(parents=True, exist_ok=True)
        if not self.exists(project_id):
            path.parent.mkdir(parents=True, exist_ok=True)
            empty_template = self._root / ".empty-template"
            empty_template.mkdir(exist_ok=True)
            self._run(None, "init", "--bare", "--quiet", f"--template={empty_template}", f"--initial-branch={MAIN}", str(path))
        head = self.head(project_id)
        if head is not None:
            return head
        commit = self._commit(path, None, [FileChange("README.md", "add", readme)], "Project repository created by Agentra", author)
        self._update_ref(path, MAIN, commit, _ZERO)
        return commit

    def commit_changes(
        self, project_id: uuid.UUID, base: str, changes: list[FileChange], message: str, author: Signature, branch: str
    ) -> str:
        """Commits the changes on top of base and points the branch at the commit (replacing what it pointed to)."""
        path = self.path(project_id)
        commit = self._commit(path, base, changes, message, author)
        self._run(path, "update-ref", "-m", "agentra: change set", f"refs/heads/{branch}", commit)
        return commit

    def merge(self, project_id: uuid.UUID, commit: str, message: str, author: Signature) -> MergeOutcome:
        """Merges a commit into main without a working tree. A conflict changes nothing and names the files."""
        path = self.path(project_id)
        main = self.head(project_id)
        if main is None:
            raise GitError("The repository has no main branch")
        if self.is_ancestor(project_id, commit, main):
            return MergeOutcome("already_merged", main)
        if self.is_ancestor(project_id, main, commit):
            new = commit  # main has not moved since the change set was based on it
        else:
            result = self._run(path, "merge-tree", "--write-tree", "--name-only", "--no-messages", main, commit, check=False)
            lines = [line for line in result.stdout.decode("utf-8", "replace").splitlines() if line]
            if result.returncode == 1:
                return MergeOutcome("conflict", main, tuple(sorted(set(lines[1:]))))
            if result.returncode != 0 or not lines:
                raise GitError(f"git merge-tree failed (exit {result.returncode})")
            new = self._commit_tree(path, lines[0], [main, commit], message, author)
        self._update_ref(path, MAIN, new, main)
        return MergeOutcome("merged", new)

    # Reads ----------------------------------------------------------------------------------------

    def head(self, project_id: uuid.UUID, branch: str = MAIN) -> str | None:
        if not self.exists(project_id):
            return None
        result = self._run(self.path(project_id), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
        if result.returncode != 0:
            return None
        return result.stdout.decode().strip() or None

    def is_ancestor(self, project_id: uuid.UUID, ancestor: str, commit: str) -> bool:
        result = self._run(self.path(project_id), "merge-base", "--is-ancestor", ancestor, commit, check=False)
        if result.returncode not in (0, 1):
            raise GitError(f"git merge-base failed (exit {result.returncode})")
        return result.returncode == 0

    def list_files(self, project_id: uuid.UUID, commit: str) -> list[RepoFile]:
        output = self._run(self.path(project_id), "ls-tree", "-r", "-z", "--long", "--full-tree", commit).stdout.decode("utf-8", "replace")
        files = []
        for entry in output.split("\x00"):
            if not entry:
                continue
            meta, name = entry.split("\t", 1)
            _mode, kind, _sha, size = meta.split()
            if kind == "blob":
                files.append(RepoFile(name, int(size)))
        return files

    def read_file(self, project_id: uuid.UUID, commit: str, path: str) -> bytes:
        if not safe_path(path):
            raise GitError("Not a repository path")
        return self._run(self.path(project_id), "cat-file", "blob", f"{commit}:{path}").stdout

    def diff(self, project_id: uuid.UUID, base: str, commit: str) -> str:
        args = ("diff", "--no-ext-diff", "--no-textconv", "--no-color", "--no-renames", "--full-index", base, commit)
        return self._run(self.path(project_id), *args).stdout.decode("utf-8", "replace")

    # Helpers --------------------------------------------------------------------------------------

    def _commit(self, path: Path, base: str | None, changes: list[FileChange], message: str, author: Signature) -> str:
        for change in changes:
            if not safe_path(change.path):
                raise GitError(f"Not a repository path: {change.path!r}")
        with tempfile.TemporaryDirectory(prefix="agentra-index-") as scratch:
            # A throwaway index, and an empty folder as the work tree git insists on; no file is ever written there.
            work_tree = Path(scratch) / "empty"
            work_tree.mkdir()
            env = {"GIT_INDEX_FILE": str(Path(scratch) / "index"), "GIT_WORK_TREE": str(work_tree)}
            if base is not None:
                self._run(path, "read-tree", base, env=env)
            for change in changes:
                if change.action == "delete":
                    self._run(path, "update-index", "--force-remove", "--", change.path, env=env)
                    continue
                data = (change.content or "").encode("utf-8")
                blob = self._run(path, "hash-object", "-w", "--no-filters", "--stdin", input=data, env=env).stdout.decode().strip()
                self._run(path, "update-index", "--add", "--cacheinfo", f"100644,{blob},{change.path}", env=env)
            tree = self._run(path, "write-tree", env=env).stdout.decode().strip()
        return self._commit_tree(path, tree, [base] if base else [], message, author)

    def _commit_tree(self, path: Path, tree: str, parents: list[str], message: str, author: Signature) -> str:
        stamp = f"{int(author.when.timestamp())} +0000"
        env = {
            "GIT_AUTHOR_NAME": author.name,
            "GIT_AUTHOR_EMAIL": author.email,
            "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_NAME": "Agentra",
            "GIT_COMMITTER_EMAIL": "agentra@agentra.local",
            "GIT_COMMITTER_DATE": stamp,
        }
        args = ["commit-tree", tree]
        for parent in parents:
            args += ["-p", parent]
        return self._run(path, *args, input=message.encode("utf-8"), env=env).stdout.decode().strip()

    def _update_ref(self, path: Path, branch: str, new: str, old: str) -> None:
        result = self._run(path, "update-ref", "-m", "agentra", f"refs/heads/{branch}", new, old, check=False)
        if result.returncode != 0:
            raise GitError(f"{branch} moved while Agentra was updating it; try again")

    def _run(
        self,
        path: Path | None,
        *args: str,
        input: bytes | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        git = shutil.which("git")
        if git is None:
            raise GitError("git is not installed on the Agentra host")
        base_env = {name: os.environ[name] for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if name in os.environ}
        base_env |= {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "HOME": str(self._root),
            "LC_ALL": "C",
        }
        settings = ["-c", f"core.hooksPath={self._no_hooks}", "-c", "core.autocrlf=false", "-c", "core.fsmonitor=false", "-c", "protocol.allow=never"]
        location = [f"--git-dir={path}"] if path is not None else []
        result = subprocess.run(
            [git, *settings, *location, *args], input=input, env=base_env | (env or {}), capture_output=True, timeout=120, check=False
        )
        if check and result.returncode != 0:
            # Only git's own message: no file contents are ever passed on the command line.
            message = result.stderr.decode("utf-8", "replace").strip().splitlines()
            raise GitError(f"git {args[0]} failed: {message[-1] if message else f'exit {result.returncode}'}")
        return result
