"""Explicit held-out execution, allowed only against a verified implementation freeze."""

import argparse
import asyncio
from pathlib import Path

from pharmacy_evaluation.config import EvaluationSettings as Settings
from pharmacy_evaluation.runners.development import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=4)
    parser.add_argument("--interval", type=float, default=15)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(Settings.from_env(), args.output, max_requests=args.max_requests,
                    resume=args.resume, interval=args.interval, split="held_out", freeze=args.freeze))


if __name__ == "__main__":
    main()
