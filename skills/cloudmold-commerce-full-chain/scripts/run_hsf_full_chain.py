#!/usr/bin/env python3
"""Run the canonical product commerce vertical with a hard Dubbo-only boundary."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    skill_dir = Path(__file__).resolve().parent.parent
    runner = skill_dir / "scripts" / "yshopping_aftersales_vertical_runner.py"
    environment = os.environ.copy()
    requested = environment.get("CLOUDMOLD_INTERNAL_TRANSPORT", "dubbo").lower()
    if requested != "dubbo":
        print("CLOUDMOLD_INTERNAL_TRANSPORT must be dubbo for this Skill", file=sys.stderr)
        return 2
    environment["CLOUDMOLD_INTERNAL_TRANSPORT"] = "dubbo"
    environment.setdefault("CLOUDMOLD_SKILL_ID", "skill.cloudmold.commerce.full-chain-hsf.v1")
    run_id = next((value.split("=", 1)[1] for value in sys.argv[1:]
                   if value.startswith("--run-id=")), None)
    if run_id is None and "--run-id" in sys.argv[1:]:
        index = sys.argv.index("--run-id")
        if index + 1 < len(sys.argv):
            run_id = sys.argv[index + 1]
    if run_id:
        environment["CLOUDMOLD_HSF_RUN_ID"] = run_id
        trace = Path.home() / ".cloudmold" / "runs" / "hsf-full" / run_id / "transport.jsonl"
        trace.parent.mkdir(parents=True, exist_ok=True)
        environment["CLOUDMOLD_HSF_TRACE_FILE"] = str(trace)
    completed = subprocess.run(
        [sys.executable, str(runner), *sys.argv[1:]],
        cwd=skill_dir,
        env=environment,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
