#!/usr/bin/env python3
"""Selectively remove CloudMold role-smoke facts from one DeerFlow memory file."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEST_SOURCE_PREFIX = "cloudmold-role-smoke-"


class CleanupError(RuntimeError):
    """Raised when a memory file cannot be cleaned safely."""


def _is_test_fact(fact: Any) -> bool:
    return (
        isinstance(fact, dict)
        and isinstance(fact.get("source"), str)
        and fact["source"].startswith(TEST_SOURCE_PREFIX)
    )


def _clear_summaries(value: Any) -> None:
    if isinstance(value, dict):
        if "summary" in value and isinstance(value["summary"], str):
            value["summary"] = ""
            if "updatedAt" in value:
                value["updatedAt"] = ""
        for child in value.values():
            _clear_summaries(child)
    elif isinstance(value, list):
        for child in value:
            _clear_summaries(child)


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    file_mode = path.stat().st_mode
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(file_mode)
    temporary.replace(path)


def cleanup_test_memory(memory_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    memory_path = memory_path.expanduser().resolve()
    try:
        document = json.loads(memory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CleanupError(f"cannot load memory file: {memory_path}") from error
    if not isinstance(document, dict):
        raise CleanupError("memory document must be a JSON object")
    facts = document.get("facts")
    if not isinstance(facts, list):
        raise CleanupError("memory document facts must be a list")

    retained_facts = [fact for fact in facts if not _is_test_fact(fact)]
    removed_count = len(facts) - len(retained_facts)
    all_facts_were_test = bool(facts) and removed_count == len(facts)
    result: dict[str, Any] = {
        "memoryPath": str(memory_path),
        "removedFactCount": removed_count,
        "retainedFactCount": len(retained_facts),
        "summariesCleared": all_facts_were_test,
        "dryRun": dry_run,
        "backupPath": None,
    }
    if removed_count == 0 or dry_run:
        return result

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = memory_path.with_name(f"{memory_path.name}.before-role-smoke-cleanup-{timestamp}.bak")
    try:
        shutil.copy2(memory_path, backup_path)
    except OSError as error:
        raise CleanupError(f"cannot create memory backup: {backup_path}") from error

    document["facts"] = retained_facts
    if all_facts_were_test:
        _clear_summaries(document.get("user"))
        _clear_summaries(document.get("history"))
    document["lastUpdated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        _atomic_write_json(memory_path, document)
    except OSError as error:
        raise CleanupError(
            f"backup created at {backup_path}, but cleaned memory could not be written"
        ) from error
    result["backupPath"] = str(backup_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-file", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = cleanup_test_memory(args.memory_file, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except CleanupError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
