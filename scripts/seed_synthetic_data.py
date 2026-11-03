"""Seeds the synthetic demo project. Same as: uv run python -m app.cli seed-demo [--admin-email ...]

Usage (from the repository root): uv run python scripts/seed_synthetic_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["seed-demo", *sys.argv[1:]]))
