"""Creates three throwaway users in the database named by DATABASE_URL (the test database) for the UI run."""

import json
import sys
import uuid

from app.cli import main

suffix = uuid.uuid4().hex[:6]
password = "ui-test-pass-123"
users = {
    "admin": (f"admin_{suffix}@ui.test", "UI Admin", True),
    "pm": (f"pm_{suffix}@ui.test", "UI Project Manager", False),
    "reviewer": (f"reviewer_{suffix}@ui.test", "UI Reviewer", False),
}
for email, name, admin in users.values():
    args = ["create-user", "--email", email, "--name", name] + (["--admin"] if admin else [])
    if main(args, read_password=lambda: password) != 0:
        sys.exit(1)

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({"suffix": suffix, "password": password, "users": {k: v[0] for k, v in users.items()}}, handle)
