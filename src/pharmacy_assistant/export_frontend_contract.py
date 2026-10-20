"""Export core OpenAPI for frontend types without starting services or reading secrets."""

import json

from pharmacy_assistant.api import create_app
from pharmacy_assistant.paths import ROOT


def main():
    target = ROOT / "frontend/contracts/core.openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported frontend/contracts/core.openapi.json (schema only; no runtime configuration).")


if __name__ == "__main__":
    main()
