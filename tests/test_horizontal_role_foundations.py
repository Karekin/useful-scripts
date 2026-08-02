import json
import importlib.util
import unittest
from pathlib import Path


CONTRACT_PATH = Path(__file__).resolve().parents[1] / 'contracts' / 'horizontal-role-foundations-v1.json'
SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'evaluate_horizontal_role_readiness.py'
EXPECTED_ROLES = {
    'enterprise-platform-operator',
    'hr-organization-operator',
    'legal-ip-operator',
    'privacy-security-operator',
    'strategy-pmo-control-operator',
}

SPEC = importlib.util.spec_from_file_location('horizontal_role_readiness', SCRIPT_PATH)
READINESS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(READINESS)


class HorizontalRoleFoundationContractTest(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
        self.roles = self.contract['roles']

    def test_contract_covers_every_unmanaged_horizontal_role(self):
        self.assertEqual(
            self.contract['schemaVersion'],
            'cloudmold.horizontal-role-foundation/v1',
        )
        self.assertEqual({role['ownerRole'] for role in self.roles}, EXPECTED_ROLES)
        self.assertEqual(len(self.roles), len(EXPECTED_ROLES))

    def test_every_role_fails_closed_until_its_foundation_is_real(self):
        for role in self.roles:
            with self.subTest(role=role['ownerRole']):
                self.assertEqual(role['stage'], 'FOUNDATION_REQUIRED')
                self.assertTrue(role['authoritySources'])
                self.assertTrue(role['controlledArtifacts'])
                self.assertTrue(role['approvalBoundary'])
                self.assertGreaterEqual(len(role['prohibitedAutomation']), 3)
                self.assertGreaterEqual(len(role['exitCriteria']), 4)

    def test_readiness_denies_drafts_when_any_authority_source_is_missing(self):
        role = next(role for role in self.roles if role['ownerRole'] == 'privacy-security-operator')

        result = READINESS.evaluate(role, {'IAM'}, responsible_owner_bound=True)

        self.assertEqual(result['status'], 'BLOCKED_MISSING_AUTHORITY_SOURCES')
        self.assertEqual(
            result['missingAuthoritySources'],
            ['SIEM', '数据分类与隐私请求系统'],
        )
        self.assertEqual(result['permittedOutcome'], [])
        self.assertFalse(result['writeAuthorityGranted'])

    def test_readiness_allows_only_controlled_drafts_after_full_foundation(self):
        role = next(role for role in self.roles if role['ownerRole'] == 'enterprise-platform-operator')

        result = READINESS.evaluate(
            role,
            set(role['authoritySources']),
            responsible_owner_bound=True,
        )

        self.assertEqual(result['status'], 'READY_FOR_GOVERNED_DRAFT')
        self.assertEqual(result['permittedOutcome'], role['controlledArtifacts'])
        self.assertFalse(result['writeAuthorityGranted'])


if __name__ == '__main__':
    unittest.main()
