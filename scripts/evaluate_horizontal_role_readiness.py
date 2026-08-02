#!/usr/bin/env python3
"""Fail-closed readiness evaluation for CloudMold horizontal role foundations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT = (
    Path(__file__).resolve().parents[1]
    / 'contracts'
    / 'horizontal-role-foundations-v1.json'
)


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding='utf-8'))
    if contract.get('schemaVersion') != 'cloudmold.horizontal-role-foundation/v1':
        raise ValueError('unsupported horizontal role foundation contract')
    return contract


def evaluate(
    role: dict[str, Any],
    available_sources: set[str],
    responsible_owner_bound: bool,
) -> dict[str, Any]:
    missing_sources = [
        source for source in role['authoritySources'] if source not in available_sources
    ]
    if missing_sources:
        status = 'BLOCKED_MISSING_AUTHORITY_SOURCES'
    elif not responsible_owner_bound:
        status = 'BLOCKED_MISSING_RESPONSIBLE_OWNER'
    else:
        status = 'READY_FOR_GOVERNED_DRAFT'

    return {
        'ownerRole': role['ownerRole'],
        'status': status,
        'missingAuthoritySources': missing_sources,
        'permittedOutcome': (
            role['controlledArtifacts'] if status == 'READY_FOR_GOVERNED_DRAFT' else []
        ),
        'approvalBoundary': role['approvalBoundary'],
        'prohibitedAutomation': role['prohibitedAutomation'],
        'writeAuthorityGranted': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument('--owner-role', required=True)
    parser.add_argument('--available-source', action='append', default=[])
    parser.add_argument('--responsible-owner-bound', action='store_true')
    args = parser.parse_args()

    contract = load_contract(args.contract)
    roles = {role['ownerRole']: role for role in contract['roles']}
    if args.owner_role not in roles:
        parser.error(f'unknown horizontal role: {args.owner_role}')
    print(
        json.dumps(
            evaluate(
                roles[args.owner_role],
                set(args.available_source),
                args.responsible_owner_bound,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
