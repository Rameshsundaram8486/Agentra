"""The project git repositories (app/modules/implementation/git_repo.py) on real git, in a temporary folder."""

import os
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.modules.implementation.git_repo import FileChange, GitError, GitRepositories, Signature, safe_path

ME = Signature("Developer Agent", "developer@agents.agentra.local", datetime(2026, 11, 6, tzinfo=UTC))


@pytest.fixture
def repos(tmp_path: Path) -> GitRepositories:
    return GitRepositories(tmp_path)


@pytest.fixture
def project(repos: GitRepositories) -> uuid.UUID:
    project_id = uuid.uuid4()
    repos.ensure(project_id, "# Leave app\n", ME)
    return project_id


def test_ensure_creates_main_once(repos: GitRepositories) -> None:
    project_id = uuid.uuid4()
    first = repos.ensure(project_id, "# Leave app\n", ME)
    assert repos.ensure(project_id, "# Something else\n", ME) == first  # the existing repository is kept
    assert repos.head(project_id) == first
    assert [f.path for f in repos.list_files(project_id, first)] == ["README.md"]
    assert repos.read_file(project_id, first, "README.md") == b"# Leave app\n"
    assert not (repos.path(project_id) / "hooks").exists()  # created from an empty template: no sample hooks


def test_a_change_set_commit_goes_to_its_branch_only(repos: GitRepositories, project: uuid.UUID) -> None:
    main = repos.head(project)
    assert main is not None
    commit = repos.commit_changes(
        project, main, [FileChange("src/leave.py", "add", "x = 1\r\n"), FileChange("README.md", "delete")], "WI-001", ME, "wi/WI-001/v1"
    )
    assert repos.head(project) == main and repos.head(project, "wi/WI-001/v1") == commit
    assert [f.path for f in repos.list_files(project, commit)] == ["src/leave.py"]
    assert repos.read_file(project, commit, "src/leave.py") == b"x = 1\r\n"  # stored exactly: no line-ending conversion
    diff = repos.diff(project, main, commit)
    assert "+++ b/src/leave.py" in diff and "--- a/README.md" in diff


def test_merges_fast_forward_combine_or_stop_on_a_conflict(repos: GitRepositories, project: uuid.UUID) -> None:
    main = repos.head(project)
    assert main is not None
    a = repos.commit_changes(project, main, [FileChange("README.md", "modify", "# A\n")], "a", ME, "wi/a")
    b = repos.commit_changes(project, main, [FileChange("README.md", "modify", "# B\n")], "b", ME, "wi/b")
    c = repos.commit_changes(project, main, [FileChange("docs/c.md", "add", "c\n")], "c", ME, "wi/c")

    merged = repos.merge(project, a, "Merge a", ME)
    assert (merged.status, merged.commit) == ("merged", a)  # main had not moved
    assert repos.merge(project, a, "Merge a", ME).status == "already_merged"
    conflict = repos.merge(project, b, "Merge b", ME)
    assert (conflict.status, conflict.conflicts, repos.head(project)) == ("conflict", ("README.md",), a)
    combined = repos.merge(project, c, "Merge c", ME)
    assert combined.status == "merged" and combined.commit not in (a, c)
    assert sorted(f.path for f in repos.list_files(project, combined.commit or "")) == ["README.md", "docs/c.md"]


@pytest.mark.parametrize("path", ["../x", ".git/config", ".GIT/config", "/abs", "a\\b", "C:/x", "a//b", "./a", " a", ""])
def test_unsafe_paths_never_reach_git(repos: GitRepositories, project: uuid.UUID, path: str) -> None:
    assert not safe_path(path)
    with pytest.raises(GitError):
        repos.commit_changes(project, repos.head(project) or "", [FileChange(path, "add", "x")], "bad", ME, "wi/bad")


def test_repository_hooks_never_run(repos: GitRepositories, project: uuid.UUID, tmp_path: Path) -> None:
    hooks = repos.path(project) / "hooks"
    hooks.mkdir()
    marker = tmp_path / "hook-ran"
    hook = hooks / "reference-transaction"
    hook.write_text(f"#!/bin/sh\necho ran > '{marker.as_posix()}'\n", newline="\n")
    hook.chmod(0o755)
    # Control: plain git does run this hook, so the check below means something.
    git = shutil.which("git")
    assert git is not None
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    main = repos.head(project) or ""
    subprocess.run([git, f"--git-dir={repos.path(project)}", "update-ref", "refs/heads/control", main], env=env, check=True)
    if not marker.exists():
        pytest.skip("this git does not run reference-transaction hooks here")
    marker.unlink()

    commit = repos.commit_changes(project, main, [FileChange("src/a.py", "add", "a\n")], "a", ME, "wi/a")
    repos.merge(project, commit, "Merge a", ME)
    assert not marker.exists()
