#!/usr/bin/env python3
"""Build a route/API/Skill coverage matrix without executing business writes."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path


SOURCE_SUFFIXES = {".ts", ".tsx", ".vue", ".js", ".jsx"}
REQUEST_RE = re.compile(
    r"requestClient\.(get|post|put|delete|download|upload)"
    r"(?:\s*<[^;]{0,600}?>)?\s*\(\s*([`'\"])(.+?)\2",
    re.DOTALL,
)
IMPORT_RE = re.compile(r"from\s+['\"]#/api(?:/([^'\"]+))?['\"]")
ERP_ROUTE_RE = re.compile(
    r"\|\s*(GET|POST|PUT|DELETE)\s*\|\s*`(/erp/[^`]+)`\s*\|\s*`([^`]+)`\s*\|"
)
ENDPOINT_LITERAL_RE = re.compile(
    r"[\"'`](/(?:admin-api/)?(?:cloudmold|erp|trade|product|wms)/[^\"'`\s?]*)"
)


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    source: str
    referenced_by: int
    skill_referenced: bool
    backend_catalogued: bool
    runtime_called: bool
    classification: str
    intent_hint: str
    development_purpose: str
    classification_evidence: str | None


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_source_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in SOURCE_SUFFIXES and "node_modules" not in path.parts
    )


def normalize_endpoint(raw: str) -> str:
    value = " ".join(raw.split())
    value = value.split("?", 1)[0]
    value = re.sub(r"\$\{[^}]+}", "{param}", value)
    if value.startswith("/admin-api/"):
        value = value[len("/admin-api") :]
    if not value.startswith("/"):
        return value
    return re.sub(r"/+", "/", value)


def extract_api_endpoints(api_root: Path, ui_root: Path) -> list[tuple[str, str, str]]:
    endpoints: list[tuple[str, str, str]] = []
    for path in iter_source_files(api_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in REQUEST_RE.finditer(text):
            endpoint = normalize_endpoint(match.group(3))
            if endpoint.startswith("/"):
                endpoints.append((match.group(1).upper(), endpoint, relative(path, ui_root)))
    return endpoints


def resolve_api_import(import_path: str | None, api_root: Path) -> Path | None:
    if not import_path:
        candidate = api_root / "index.ts"
        return candidate if candidate.exists() else None
    clean = import_path.split("?", 1)[0]
    candidates = [api_root / f"{clean}.ts", api_root / clean / "index.ts"]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def collect_api_references(source_root: Path, api_root: Path) -> Counter[str]:
    references: Counter[str] = Counter()
    for path in iter_source_files(source_root):
        if api_root in path.parents:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in IMPORT_RE.finditer(text):
            target = resolve_api_import(match.group(1), api_root)
            if target:
                references[target.relative_to(source_root.parent).as_posix()] += 1
    return references


def collect_skill_endpoints(skill_root: Path) -> set[str]:
    endpoints: set[str] = set()
    if not skill_root.exists():
        return endpoints
    for path in skill_root.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".json", ".md", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        endpoints.update(normalize_endpoint(match.group(1)) for match in ENDPOINT_LITERAL_RE.finditer(text))
    return endpoints


def collect_erp_catalog(catalog: Path) -> set[tuple[str, str]]:
    if not catalog.exists():
        return set()
    text = catalog.read_text(encoding="utf-8", errors="replace")
    return {(verb, normalize_endpoint(route)) for verb, route, _ in ERP_ROUTE_RE.findall(text)}


def collect_runtime_calls(runtime_report: Path | None) -> set[tuple[str, str]]:
    if not runtime_report or not runtime_report.exists():
        return set()
    payload = json.loads(runtime_report.read_text(encoding="utf-8"))
    calls: set[tuple[str, str]] = set()
    for route in payload.get("routes", []):
        for request in route.get("api_calls", []):
            calls.add((request.get("method", "GET").upper(), normalize_endpoint(request.get("path", ""))))
    return calls


def load_overrides(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("overrides", [])


def find_override(path: str, overrides: list[dict]) -> dict | None:
    for override in overrides:
        if path in override.get("paths", []):
            return override
        prefix = override.get("path_prefix")
        if prefix and path.startswith(prefix):
            return override
    return None


def intent_for(path: str) -> str:
    if path.startswith("/erp/"):
        return "legacy_yudao_erp_operational_surface"
    if path.startswith("/wms/"):
        return "legacy_wms_physical_operation_surface"
    if path.startswith(("/trade/", "/product/")):
        return "legacy_mall_commerce_surface"
    if path.startswith("/cloudmold/"):
        return "canonical_cloudmold_atomic_surface"
    return "shared_platform_surface"


def classify(*, referenced: int, skill_referenced: bool, runtime_called: bool) -> str:
    if runtime_called:
        return "EXECUTED_BY_UI_SMOKE"
    if skill_referenced or referenced:
        return "TEST_GAP"
    return "REDUNDANCY_CANDIDATE"


def domain_from_source(source: str) -> str:
    marker = "src/api/"
    if marker not in source:
        return "unknown"
    tail = source.split(marker, 1)[1]
    return tail.split("/", 1)[0]


def build_report(
    workspace: Path,
    runtime_report: Path | None = None,
    ui_root: Path | None = None,
    skill_root: Path | None = None,
    erp_catalog: Path | None = None,
    classification_overrides: Path | None = None,
) -> dict:
    ui_root = ui_root or workspace / "yudao-ui-admin-vben"
    app_root = ui_root / "apps/web-antd/src"
    api_root = app_root / "api"
    skill_root = skill_root or Path(
        "/Users/karekin/Library/Mobile Documents/iCloud~md~obsidian/Documents/project/Agent Skills/cloudmold-erp-operator"
    )
    erp_catalog = erp_catalog or Path(
        "/Users/karekin/.codex/skills/cloudmold-project/references/erp-rest-catalog.md"
    )
    classification_overrides = classification_overrides or (
        Path(__file__).resolve().parent.parent / "references/coverage-classification-overrides-v1.json"
    )

    source_files = iter_source_files(app_root)
    view_files = iter_source_files(app_root / "views")
    api_files = iter_source_files(api_root)
    all_tests = [
        path
        for path in iter_source_files(ui_root)
        if re.search(r"(?:^|/)(?:__tests__/.*|[^/]+\.(?:test|spec))\.(?:ts|tsx|js|jsx|vue)$", path.as_posix())
    ]
    business_tests = [path for path in all_tests if app_root in path.parents]

    references = collect_api_references(app_root, api_root)
    skill_endpoints = collect_skill_endpoints(skill_root)
    backend_routes = collect_erp_catalog(erp_catalog)
    runtime_calls = collect_runtime_calls(runtime_report)
    overrides = load_overrides(classification_overrides)

    endpoint_rows: list[Endpoint] = []
    for method, path, source in extract_api_endpoints(api_root, ui_root):
        source_key = source.split("apps/web-antd/", 1)[-1]
        referenced_by = references.get(source_key, 0)
        skill_referenced = path in skill_endpoints
        runtime_called = (method, path) in runtime_calls or any(
            called_path == path for _, called_path in runtime_calls
        )
        initial_classification = classify(
            referenced=referenced_by,
            skill_referenced=skill_referenced,
            runtime_called=runtime_called,
        )
        override = find_override(path, overrides) if not runtime_called else None
        final_classification = override.get("classification") if override else initial_classification
        endpoint_rows.append(
            Endpoint(
                method=method,
                path=path,
                source=source,
                referenced_by=referenced_by,
                skill_referenced=skill_referenced,
                backend_catalogued=(method, path) in backend_routes,
                runtime_called=runtime_called,
                classification=final_classification,
                intent_hint=intent_for(path),
                development_purpose=(
                    override.get("development_purpose")
                    if override
                    else "UI API wrapper for the declared module; inspect workflow ownership before deletion"
                ),
                classification_evidence=override.get("evidence") if override else None,
            )
        )

    classification_counts = Counter(row.classification for row in endpoint_rows)
    domain_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in endpoint_rows:
        domain = domain_from_source(row.source)
        domain_counts[domain]["endpoints"] += 1
        domain_counts[domain][row.classification] += 1

    runtime_payload = None
    if runtime_report and runtime_report.exists():
        runtime_payload = json.loads(runtime_report.read_text(encoding="utf-8"))

    return {
        "schema_version": "cloudmold.coverage-audit/v1",
        "scope": {
            "workspace": str(workspace),
            "ui_root": str(ui_root),
            "skill_root": str(skill_root),
            "erp_catalog": str(erp_catalog),
            "classification_overrides": str(classification_overrides),
        },
        "denominators": {
            "web_antd_source_files": len(source_files),
            "web_antd_view_files": len(view_files),
            "web_antd_api_files": len(api_files),
            "ui_test_files_total": len(all_tests),
            "web_antd_business_test_files": len(business_tests),
            "ui_api_endpoints": len(endpoint_rows),
            "erp_backend_catalog_routes": len(backend_routes),
            "skill_endpoint_literals": len(skill_endpoints),
            "runtime_api_calls": len(runtime_calls),
        },
        "summary": {
            "classifications": dict(sorted(classification_counts.items())),
            "domains": {domain: dict(values) for domain, values in sorted(domain_counts.items())},
            "canonical_ui_endpoint_count": sum(row.path.startswith("/cloudmold/") for row in endpoint_rows),
            "legacy_erp_ui_endpoint_count": sum(row.path.startswith("/erp/") for row in endpoint_rows),
            "business_test_gap": len(business_tests) == 0,
        },
        "runtime_summary": runtime_payload.get("summary") if runtime_payload else None,
        "endpoints": [asdict(row) for row in endpoint_rows],
        "interpretation": {
            "zero_coverage_is_dead_code": False,
            "redundancy_candidate_requires_manual_review": True,
            "generated_framework_code_is_business_denominator": False,
        },
    }


def render_markdown(report: dict) -> str:
    d = report["denominators"]
    s = report["summary"]
    lines = [
        "# CloudMold full-chain coverage audit",
        "",
        "## Denominators",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| `{key}` | {value} |" for key, value in d.items())
    lines.extend(
        [
            "",
            "## Classification",
            "",
            "| Classification | Endpoint count |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| `{key}` | {value} |" for key, value in s["classifications"].items())
    lines.extend(
        [
            "",
            "## Architectural signals",
            "",
            f"- Business tests inside `apps/web-antd/src`: **{d['web_antd_business_test_files']}**.",
            f"- Canonical `/cloudmold/**` UI endpoints: **{s['canonical_ui_endpoint_count']}**.",
            f"- Legacy `/erp/**` UI endpoints: **{s['legacy_erp_ui_endpoint_count']}**.",
            "- `REDUNDANCY_CANDIDATE` means no consumer/evidence was found by this scanner; it is not a deletion decision.",
            "- Runtime function coverage is transformed-code smoke evidence, not source-line coverage.",
            "",
            "## Highest-risk uncovered endpoints",
            "",
            "| Class | Method | Path | Intent | Source |",
            "|---|---|---|---|---|",
        ]
    )
    risky = [
        row
        for row in report["endpoints"]
        if row["classification"] in {"FLOW_GAP", "REDUNDANCY_CANDIDATE"}
    ][:100]
    lines.extend(
        f"| `{row['classification']}` | {row['method']} | `{row['path']}` | `{row['intent_hint']}` | `{row['source']}` |"
        for row in risky
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--ui-root", type=Path)
    parser.add_argument("--skill-root", type=Path)
    parser.add_argument("--erp-catalog", type=Path)
    parser.add_argument("--runtime-report", type=Path)
    parser.add_argument("--classification-overrides", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        workspace=args.workspace.resolve(),
        runtime_report=args.runtime_report,
        ui_root=args.ui_root,
        skill_root=args.skill_root,
        erp_catalog=args.erp_catalog,
        classification_overrides=args.classification_overrides,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "coverage.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), **report["denominators"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
