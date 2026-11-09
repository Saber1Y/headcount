"""Command line entry: python -m headcount <step>."""

from __future__ import annotations

import argparse
from pathlib import Path

DATA = Path("data")


def main() -> None:
    parser = argparse.ArgumentParser(prog="headcount")
    parser.add_argument(
        "step",
        choices=["sample", "apps", "enrich", "report", "export", "all"],
        help="pipeline step to run",
    )
    args = parser.parse_args()
    steps = ["sample", "apps", "enrich", "report", "export"] if args.step == "all" else [args.step]
    for step in steps:
        if step == "sample":
            from . import sample

            sample.run(DATA / "windows")
        elif step == "apps":
            from . import apps

            apps.run(DATA)
        elif step == "enrich":
            from . import enrich

            enrich.run(DATA)
        elif step == "report":
            from . import report

            report.run(DATA)
        elif step == "export":
            from . import export

            export.run(DATA)


if __name__ == "__main__":
    main()
