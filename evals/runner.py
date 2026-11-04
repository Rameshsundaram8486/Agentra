"""Runs eval cases and scores them. Before changing a model, prompt, effort or guardrail, run it and compare.

    uv run python -m evals.runner                        # replay recorded answers: free
    uv run python -m evals.runner --mode live --cap 5    # call Claude, record the answers (costs money)
    uv run python -m evals.runner --cases clarify_*      # a subset
    uv run python -m evals.runner --update-baseline      # accept these results as the new baseline

Runs only against the TEST database (TEST_DATABASE_URL, name ending in _test), on throwaway projects.
Live mode stops before a case whose worst-case cost would take the run past the cap. Replay re-grades the
recorded answers through the current guardrails, quality checks and graders; it does not re-test the prompt.
Results go to var/evals/<time>/; a grader that passed in the committed baseline and fails now is a regression
(exit code 1).
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app.composition import load_policies
from app.infrastructure.db import create_db_engine, make_session_factory
from app.infrastructure.logging import configure_logging
from app.infrastructure.settings import ENV_FILE, ROOT_DIR, Settings
from app.infrastructure.storage.local import LocalArtifactStore
from app.model_gateway.providers.anthropic_provider import AnthropicProvider
from app.model_gateway.providers.base import Attempt, Provider, TokenUsage
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.model_gateway.telemetry import worst_case_cost
from evals.cases import EVALS_DIR, Case, load_cases
from evals.graders import grade, score
from evals.scenario import RecordingProvider, Scenario

PROMPT_CHARS_MARGIN = 20_000  # the system prompt and the framing around the documents


class _EvalEnvironment(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_ignore_empty=True, extra="ignore")

    test_database_url: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None


class EvalSetupError(Exception):
    pass


def _test_database(url: str | None) -> str:
    if url is None:
        configured = _EvalEnvironment().test_database_url
        url = configured.get_secret_value() if configured else None
    if not url:
        raise EvalSetupError("TEST_DATABASE_URL is not set in .env")
    if not (make_url(url).database or "").endswith("_test"):
        raise EvalSetupError("Evals run only against a database whose name ends in '_test'")
    return url


def _paths(root: Path, case: Case) -> tuple[Path, Path]:
    base = root / case.agent
    return base / "recordings" / f"{case.id}.json", base / "baselines" / f"{case.id}.json"


def _read(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _replay_provider(recording: dict[str, Any]) -> Provider:
    usage = TokenUsage(**recording.get("usage", {}))
    response = fake_response(
        recording["text"], model=recording["model"], stop_reason=recording.get("stop_reason") or "end_turn", usage=usage,
        attempts=(Attempt(recording["model"], usage),),
    )
    return RecordingProvider(FakeProvider([response]))


def main(
    argv: Sequence[str] | None = None,
    *,
    database_url: str | None = None,
    root: Path = EVALS_DIR,
    out_dir: Path | None = None,
    live_provider: Callable[[], Provider] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.runner", description="Agentra agent evals")
    parser.add_argument("--mode", choices=["replay", "live"], default="replay")
    parser.add_argument("--cases", default="*", help="Case file name pattern, e.g. clarify_*")
    parser.add_argument("--cap", type=Decimal, default=Decimal("5"), help="Live mode: maximum model spend for this run, USD")
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)

    try:
        url = _test_database(database_url)
    except EvalSetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    settings = Settings(database_url=url, agentra_env="test")
    configure_logging("WARNING", settings.secret_values())
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")

    out_dir = out_dir or ROOT_DIR / "var" / "evals"
    policies = load_policies()
    engine = create_db_engine(url)
    scenario = Scenario(make_session_factory(engine), policies, LocalArtifactStore(out_dir / "store"))
    cases = load_cases(root, args.cases)
    if args.mode == "live" and live_provider is None:
        key = _EvalEnvironment().anthropic_api_key
        if key is None:
            print("error: ANTHROPIC_API_KEY is not set in .env", file=sys.stderr)
            return 2
        live_provider = lambda: AnthropicProvider(key.get_secret_value())  # noqa: E731

    spent = Decimal(0)
    rows: list[dict[str, Any]] = []
    for case in cases:
        definition = policies.agents.task(case.agent, case.task)
        assert definition is not None
        recording_path, baseline_path = _paths(root, case)
        row: dict[str, Any] = {"case": case.id, "task": case.task, "prompt_version": definition.prompt.version, "notes": []}
        if args.mode == "live":
            profile = policies.models.profile(case.agent, case.task).model_copy(update={"refusal_fallback": False})
            prompt_chars = len(case.brief) + sum(len(d.content) for d in case.documents) + PROMPT_CHARS_MARGIN
            worst = worst_case_cost(policies.models, profile, prompt_chars)
            if spent + worst > args.cap:
                row.update(status="skipped", reason=f"cap: ${spent:.2f} spent, this case could cost up to ${worst:.2f}")
                rows.append(row)
                continue
            provider: Provider = RecordingProvider(live_provider())  # type: ignore[misc]
        else:
            recording = _read(recording_path)
            if recording is None:
                row.update(status="skipped", reason="no recording; run in live mode first")
                rows.append(row)
                continue
            if recording.get("prompt_version") != definition.prompt.version:
                row["notes"].append(f"recorded with prompt {recording.get('prompt_version')}; replay grades that answer")
            provider = _replay_provider(recording)

        outcome = scenario.run(case, provider)
        cost = Decimal(outcome.run.cost_usd) if args.mode == "live" else Decimal(0)
        spent += cost
        if args.mode == "live":
            call = outcome.run.model_calls[-1] if outcome.run.model_calls else None
            response = provider.responses[-1] if getattr(provider, "responses", None) else None  # type: ignore[attr-defined]
            _write(recording_path, {
                "case_id": case.id,
                "task": case.task,
                "prompt_version": outcome.run.prompt_version,
                "model": call.model if call else None,
                "stop_reason": call.stop_reason if call else None,
                "usage": {
                    "input_tokens": call.input_tokens if call else 0,
                    "output_tokens": call.output_tokens if call else 0,
                    "cache_creation_input_tokens": call.cache_creation_input_tokens if call else 0,
                    "cache_read_input_tokens": call.cache_read_input_tokens if call else 0,
                },
                "cost_usd": str(outcome.run.cost_usd),
                "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "text": response.text if response else "",
            })
        results = grade(case, outcome)
        baseline = _read(baseline_path)
        regressions = [r.name for r in results if baseline and baseline["results"].get(r.name) is True and not r.passed]
        row.update(
            status="graded",
            score=round(score(results), 3),
            cost_usd=str(cost),
            results=[r.to_dict() for r in results],
            regressions=regressions,
            baseline=bool(baseline),
        )
        if args.update_baseline:
            _write(baseline_path, {
                "case_id": case.id,
                "prompt_version": outcome.run.prompt_version,
                "score": row["score"],
                "results": {r.name: r.passed for r in results},
                "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            })
        rows.append(row)
    engine.dispose()

    report_dir = out_dir / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    _write(report_dir / "results.json", {"mode": args.mode, "cap_usd": str(args.cap), "spent_usd": str(spent), "cases": rows})
    (report_dir / "report.md").write_text(_markdown(args.mode, spent, rows), encoding="utf-8")
    print(_summary(args.mode, spent, rows, report_dir))
    return 1 if any(row.get("regressions") for row in rows) else 0


def _markdown(mode: str, spent: Decimal, rows: list[dict[str, Any]]) -> str:
    lines = [f"# Agentra evals ({mode})", "", f"Model spend: ${spent:.2f}", ""]
    for row in rows:
        if row["status"] != "graded":
            lines += [f"## {row['case']}: skipped", "", row["reason"], ""]
            continue
        lines += [f"## {row['case']} ({row['task']}): {row['score']:.0%}", "", f"Prompt {row['prompt_version']}; cost ${row['cost_usd']}", ""]
        lines += [*(f"- Note: {note}" for note in row["notes"])]
        if row["regressions"]:
            lines.append(f"- REGRESSION: {', '.join(row['regressions'])}")
        lines += [f"- {'pass' if r['passed'] else 'FAIL'} {r['name']}: {r['detail']}" for r in row["results"]]
        lines.append("")
    return "\n".join(lines)


def _summary(mode: str, spent: Decimal, rows: list[dict[str, Any]], report_dir: Path) -> str:
    lines = [f"Evals ({mode}), model spend ${spent:.2f}"]
    for row in rows:
        if row["status"] != "graded":
            lines.append(f"  {row['case']:<32} skipped: {row['reason']}")
            continue
        failed = [r["name"] for r in row["results"] if not r["passed"]]
        flag = " REGRESSION" if row["regressions"] else ""
        lines.append(f"  {row['case']:<32} {row['score']:>5.0%}{flag}" + (f"  failed: {', '.join(failed)}" if failed else ""))
    lines.append(f"Report: {report_dir / 'report.md'}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

