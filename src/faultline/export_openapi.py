"""Export the OpenAPI schema to docs/openapi.json (the committed contract)."""

import json
from pathlib import Path

from faultline.app import app

TARGET = Path("docs/openapi.json")


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
