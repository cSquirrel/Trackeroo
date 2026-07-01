"""Export the live FastAPI OpenAPI schema to docs/openapi.json.

Run after any route/schema change so the committed contract never drifts
from the actual implementation: `python -m app.export_openapi`
"""

from __future__ import annotations

import json
from pathlib import Path

from .main import app

OUTPUT_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
