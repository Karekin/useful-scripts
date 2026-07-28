import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts/provision_role_agents.py"
SPEC = importlib.util.spec_from_file_location("provision_role_agents", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

VERIFY_SCRIPT = SKILL_ROOT / "scripts/verify_role_agent.py"
VERIFY_SPEC = importlib.util.spec_from_file_location("verify_role_agent", VERIFY_SCRIPT)
VERIFY_MODULE = importlib.util.module_from_spec(VERIFY_SPEC)
assert VERIFY_SPEC.loader is not None
import sys
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
VERIFY_SPEC.loader.exec_module(VERIFY_MODULE)

CLEANUP_SCRIPT = SKILL_ROOT / "scripts/cleanup_test_memory.py"
CLEANUP_SPEC = importlib.util.spec_from_file_location("cleanup_test_memory", CLEANUP_SCRIPT)
CLEANUP_MODULE = importlib.util.module_from_spec(CLEANUP_SPEC)
assert CLEANUP_SPEC.loader is not None
CLEANUP_SPEC.loader.exec_module(CLEANUP_MODULE)


class RoleAgentContractTest(unittest.TestCase):
    def setUp(self):
        self.roles = MODULE.load_roles(SKILL_ROOT / "references/role-contracts.json")
        self.policies = MODULE.load_role_policies(SKILL_ROOT / "references/role-policies.json")

    def test_contract_contains_the_six_operational_roles(self):
        self.assertEqual(
            {role["display_name"] for role in self.roles},
            {"企划Agent", "买手Agent", "招商Agent", "库控Agent", "客服Agent", "体验Agent"},
        )
        self.assertEqual(len(self.roles), 6)

    def test_agent_request_is_restricted_to_role_workbench(self):
        for role in self.roles:
            policy = self.policies[role["name"]]
            request = MODULE.build_agent_request(role, policy)
            self.assertEqual(request["display_name"], role["display_name"])
            self.assertEqual(
                request["skills"],
                ["cloudmold-role-workbench", policy["policy_skill"]],
            )
            self.assertEqual(request["tool_groups"], [])
            self.assertIn(role["display_name"], request["soul"])
            self.assertIn("真实运营岗位", request["soul"])
            self.assertIn("请你确认", request["soul"])
            self.assertIn("cloudmold.deerflow-decision/v1", request["soul"])
            self.assertIn("不得生成 tenant", request["soul"])

    def test_shared_skill_fails_closed_until_role_policy_is_attached(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("allowed-tools: []", skill_text)

    def test_role_policy_contract_has_one_read_alias_per_role(self):
        self.assertEqual(set(self.policies), {role["name"] for role in self.roles})
        aliases = {policy["mcp_alias"] for policy in self.policies.values()}
        policy_ids = {policy["policy_id"] for policy in self.policies.values()}
        self.assertEqual(len(aliases), 6)
        self.assertEqual(len(policy_ids), 6)
        for policy in self.policies.values():
            self.assertEqual(policy["authority_id"], "cloudmold-agent-control-plane")
            self.assertEqual(
                policy["allowed_tools"],
                [
                    "ask_clarification",
                    f"{policy['mcp_alias']}_cloudmold_analytics_dashboard_snapshot",
                ],
            )
            self.assertFalse(
                any(
                    marker in tool_name
                    for tool_name in policy["allowed_tools"]
                    for marker in ("skill_task_submit", "skill_task_get", "skill_task_retry")
                )
            )
            self.assertEqual(
                policy["allowed_raw_mcp_tools"],
                ["cloudmold_analytics_dashboard_snapshot"],
            )
            self.assertEqual(policy["skill_task"], {"submit": [], "read": [], "retry": []})

    def test_role_policy_metric_ids_exist_in_the_locked_dashboard_snapshot(self):
        snapshot_path = (
            SKILL_ROOT.parents[1]
            / "yml/yshopping-lakehouse/analytics/apps/cloudmold-analytics/app/data/dashboard-snapshot.json"
        )
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        available_metric_ids = set(snapshot["metrics"])
        for policy in self.policies.values():
            metric_ids = policy["allowed_metric_ids"]
            self.assertTrue(metric_ids)
            self.assertEqual(len(metric_ids), len(set(metric_ids)))
            self.assertEqual(
                set(metric_ids) - available_metric_ids,
                set(),
                policy["role_name"],
            )

    def test_checked_in_policy_skills_match_machine_contract(self):
        for policy in self.policies.values():
            policy_skill = (
                SKILL_ROOT.parent / policy["policy_skill"] / "SKILL.md"
            )
            self.assertEqual(
                policy_skill.read_text(encoding="utf-8"),
                MODULE.render_policy_skill(policy),
            )

    def test_skill_manifest_and_contract_are_valid_json(self):
        manifest = json.loads((SKILL_ROOT / "skill.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "cloudmold-role-workbench")
        self.assertEqual(manifest["risk_level"], "R1")

    def test_role_tool_policy_rejects_generic_capability_invocation(self):
        with self.assertRaises(VERIFY_MODULE.ProvisionError):
            VERIFY_MODULE.assert_tool_policy([
                {
                    "type": "tool",
                    "name": "cloudmold-hsf_cloudmold_capability_read_invoke",
                }
            ], self.policies["cloudmold-inventory-control-agent"])

    def test_role_tool_policy_rejects_skill_task_tools(self):
        policy = self.policies["cloudmold-inventory-control-agent"]
        for tool_name in (
            "cloudmold-hsf_cloudmold_skill_task_submit_commerce_full_chain_r3",
            "cloudmold-hsf_cloudmold_skill_task_get",
            "cloudmold-hsf_cloudmold_skill_task_retry",
        ):
            with self.subTest(tool_name=tool_name), self.assertRaises(
                VERIFY_MODULE.ProvisionError
            ):
                VERIFY_MODULE.assert_tool_policy(
                    [{"type": "tool", "name": tool_name}], policy
                )

    def test_verify_propagates_internal_test_metadata_to_run(self):
        role = self.roles[0]
        policy = self.policies[role["name"]]
        calls = []

        def fake_request(method, url, headers, body=None, *, timeout=30):
            calls.append((method, url, body))
            if method == "GET":
                return 200, {}
            if url.endswith("/api/threads"):
                return 201, {}
            return 200, {
                "values": {
                    "messages": [
                        {
                            "type": "assistant",
                            "content": "今日判断：当前数据暂不可用，今天不能据此调整经营计划。需要关注：缺少本岗位受治理快照、业务对象范围和截止时间，现阶段没有足够证据判断优先级。建议动作：请补齐上述数据后再重新判断，在结果确认前暂不执行任何业务变更，也不向其他岗位下发任务。",
                        }
                    ]
                }
            }

        with patch.object(VERIFY_MODULE, "load_cookie_header", return_value=("cookie", "csrf")), patch.object(
            VERIFY_MODULE, "request_json", side_effect=fake_request
        ):
            VERIFY_MODULE.verify("http://deerflow", Path("cookie"), role, policy, "测试", "model")

        create_body = calls[1][2]
        run_body = calls[2][2]
        self.assertEqual(run_body["metadata"], create_body["metadata"])
        self.assertEqual(run_body["metadata"]["visibility"], "internal_test")
        self.assertEqual(run_body["metadata"]["agent_name"], role["name"])


class CleanupTestMemoryTest(unittest.TestCase):
    def _write_memory(self, root: Path, facts: list[dict], summary: str = "test summary") -> Path:
        path = root / "memory.json"
        path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "lastUpdated": "old",
                    "user": {"workContext": {"summary": summary, "updatedAt": "old"}},
                    "history": {"recentMonths": {"summary": summary, "updatedAt": "old"}},
                    "facts": facts,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_cleanup_removes_only_smoke_facts_and_keeps_mixed_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_memory(
                Path(tmp),
                [
                    {"id": "test", "source": "cloudmold-role-smoke-agent-1"},
                    {"id": "real", "source": "business-thread-1"},
                ],
            )
            result = CLEANUP_MODULE.cleanup_test_memory(path)
            cleaned = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(cleaned["facts"], [{"id": "real", "source": "business-thread-1"}])
            self.assertEqual(cleaned["user"]["workContext"]["summary"], "test summary")
            self.assertTrue(Path(result["backupPath"]).exists())

    def test_cleanup_clears_summaries_when_all_facts_are_smoke_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_memory(
                Path(tmp),
                [{"id": "test", "source": "cloudmold-role-smoke-agent-1"}],
            )
            CLEANUP_MODULE.cleanup_test_memory(path)
            cleaned = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(cleaned["facts"], [])
            self.assertEqual(cleaned["user"]["workContext"]["summary"], "")
            self.assertEqual(cleaned["history"]["recentMonths"]["summary"], "")

    def test_cleanup_does_not_create_backup_when_no_test_facts_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_memory(
                Path(tmp), [{"id": "real", "source": "business-thread-1"}]
            )
            result = CLEANUP_MODULE.cleanup_test_memory(path)
            self.assertIsNone(result["backupPath"])
            self.assertEqual(result["removedFactCount"], 0)


if __name__ == "__main__":
    unittest.main()
