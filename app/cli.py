"""Admin command line. Acts as the Agentra system account, so its actions are audited as such.

    uv run python -m app.cli create-user --email founder@example.com --name "Founder" --admin
    uv run python -m app.cli create-agent --key business_analyst --name "Business Analyst Agent"
    uv run python -m app.cli verify-audit
    uv run python -m app.cli seed-demo --admin-email admin@agentra.local

Migrations: uv run alembic upgrade head
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from app.composition import Services, load_policies
from app.demo import seed_demo
from app.infrastructure.clock import SystemClock
from app.infrastructure.db import create_db_engine, make_session_factory
from app.infrastructure.logging import configure_logging
from app.infrastructure.settings import Settings, get_settings
from app.infrastructure.storage.local import LocalArtifactStore
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.errors import DomainError, ValidationFailedError
from app.modules.identity.service import SYSTEM_ACTOR


def _prompt_password() -> str:
    first = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != first:
        raise ValidationFailedError("Passwords do not match")
    return first


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Agentra admin commands")
    commands = parser.add_subparsers(dest="command", required=True)

    user = commands.add_parser("create-user", help="Create a person who can sign in")
    user.add_argument("--email", required=True)
    user.add_argument("--name", required=True)
    user.add_argument("--admin", action="store_true", help="Platform administrator (can create projects and users)")

    agent = commands.add_parser("create-agent", help="Create an agent service account (cannot sign in)")
    agent.add_argument("--key", required=True, help="Agent key, e.g. business_analyst")
    agent.add_argument("--name", required=True)

    commands.add_parser("verify-audit", help="Check the audit hash chain end to end")

    demo = commands.add_parser("seed-demo", help="Create the synthetic demo project (safe to re-run)")
    demo.add_argument("--admin-email", default="admin@agentra.local", help="Existing platform admin who owns the demo")
    demo.add_argument("--author-email", default="pm@agentra.local", help="Demo project manager; prompted for a password if new")
    demo.add_argument("--customer-email", default="customer@agentra.local", help="Demo customer approver; prompted for a password if new")
    demo.add_argument("--code", default="DEMO-LEAVE")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    read_password: Callable[[], str] = _prompt_password,
) -> int:
    args = _parser().parse_args(argv)
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    engine = create_db_engine(settings.database_url.get_secret_value())
    try:
        with UnitOfWork(make_session_factory(engine)) as uow:
            services = Services(
                uow.session,
                SystemClock(),
                load_policies(min_password_length=settings.min_password_length),
                LocalArtifactStore(settings.artifact_root),
            )
            if args.command == "create-user":
                user = services.identity.create_user(
                    SYSTEM_ACTOR,
                    email=args.email,
                    display_name=args.name,
                    password=read_password(),
                    is_platform_admin=args.admin,
                )
                uow.commit()
                role = "platform administrator" if user.is_platform_admin else "user"
                print(f"Created {role} {user.email} ({user.id})")
            elif args.command == "create-agent":
                agent = services.identity.create_user(
                    SYSTEM_ACTOR,
                    email=f"{args.key}@agents.agentra.local",
                    display_name=args.name,
                    kind="agent",
                    agent_key=args.key,
                )
                uow.commit()
                print(f"Created agent account {agent.agent_key} ({agent.id})")
            elif args.command == "seed-demo":
                lines = seed_demo(
                    services,
                    admin_email=args.admin_email,
                    author_email=args.author_email,
                    customer_email=args.customer_email,
                    code=args.code,
                    read_password=read_password,
                )
                uow.commit()
                print("\n".join(lines))
            else:
                result = services.audit.verify_chain()
                if not result.ok:
                    print(f"Audit chain BROKEN at event {result.first_broken_seq} ({result.events_checked} verified before it)")
                    return 2
                print(f"Audit chain OK ({result.events_checked} events)")
        return 0
    except DomainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
