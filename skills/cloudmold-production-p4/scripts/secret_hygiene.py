#!/usr/bin/env python3
"""Report tracked plaintext secret candidates without printing their values."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ASSIGNMENT = re.compile(
    r"""^\s*
    (?P<key>[A-Za-z0-9_.-]*
      (?:api[-_]?key|secret[-_]?key|secret|password|passwd|access[-_]?token|
         private[-_]?key|client[-_]?secret|fernet[-_]?key)
      [A-Za-z0-9_.-]*)
    \s*[:=]\s*(?P<value>.*?)(?:\s+\#.*)?$""",
    re.IGNORECASE | re.VERBOSE,
)
JAVA_LITERAL = re.compile(
    r"(?P<key>apiKey|secretKey|privateKey|clientSecret|accessToken)"
    r'\s*=\s*"(?P<value>[^"]+)"',
    re.IGNORECASE,
)
SAFE_VALUES = {
    "",
    "''",
    '""',
    "null",
    "~",
    "false",
    "change_me",
    "changeme",
    "example",
    "dummy",
}
TEXT_SUFFIXES = {
    ".yaml",
    ".yml",
    ".properties",
    ".toml",
    ".json",
    ".xml",
    ".java",
    ".kt",
    ".py",
    ".js",
    ".ts",
    ".vue",
    ".sh",
}


def _tracked(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [
        root / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _safe(value: str) -> bool:
    normalized = value.strip().strip(",")
    if normalized.lower() in SAFE_VALUES:
        return True
    if normalized.startswith("${") and normalized.endswith("}"):
        return True
    if normalized.startswith("secret://") or normalized.startswith("kms://"):
        return True
    return False


def scan(root: Path) -> dict:
    findings: list[dict[str, object]] = []
    for path in _tracked(root):
        relative = path.relative_to(root)
        if path.name == ".env":
            findings.append(
                {
                    "path": str(relative),
                    "line": 1,
                    "key": "TRACKED_DOTENV",
                    "reason": "tracked .env files are forbidden",
                }
            )
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for number, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if not stripped or stripped.startswith(("#", "//", "*")):
                continue
            match = ASSIGNMENT.match(line)
            if match and not _safe(match.group("value")):
                findings.append(
                    {
                        "path": str(relative),
                        "line": number,
                        "key": match.group("key"),
                        "reason": "literal configured secret candidate",
                    }
                )
                continue
            match = JAVA_LITERAL.search(line)
            if match and not _safe(match.group("value")):
                findings.append(
                    {
                        "path": str(relative),
                        "line": number,
                        "key": match.group("key"),
                        "reason": "literal source secret candidate",
                    }
                )
    return {
        "contract_id": "cloudmold.production-p4.secret-hygiene.v1",
        "repository": str(root.resolve()),
        "status": "CLEAN" if not findings else "BLOCKED",
        "finding_count": len(findings),
        "findings": findings,
        "values_redacted": True,
        "history_scanned": False,
        "production_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.repository)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "CLEAN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
