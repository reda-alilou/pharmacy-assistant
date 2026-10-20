"""Export core OpenAPI for frontend types without starting services or reading secrets."""

import json
import argparse
from pathlib import Path

from pharmacy_core.api.app import create_app
from pharmacy_infrastructure.paths import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / "apps/web/contracts/core.openapi.json")
    args=parser.parse_args()
    target = args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported core OpenAPI (schema only; no runtime configuration).")


if __name__ == "__main__":
    main()
