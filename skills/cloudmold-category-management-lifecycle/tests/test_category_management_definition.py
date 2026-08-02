import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_category_management_is_a_catalog_owned_r3_business_role_sop():
    manifest = load_json("skill.json")
    definition = load_json("skill-task.json")

    assert manifest["skill_id"] == "skill.cloudmold.catalog.category-management-lifecycle.v1"
    assert manifest["owner"] == "cloudmold-catalog"
    assert manifest["authority"] == "manual-evidence-gated"
    assert manifest["risk_level"] == "R3"
    assert manifest["allowed_environments"] == ["local", "test", "demo"]
    assert definition["workflow_level"] == "BUSINESS_ROLE_SOP"
    assert definition["owner_role"] == "category-manager"
    assert definition["execution_mode"] == "MANUAL_EVIDENCE_GATED"
    assert definition["runnable"] is False
    assert definition["implementation_status"] == "SOP_ONLY_NO_CATEGORY_MANAGEMENT_EXECUTOR_CAPABILITY"


def test_definition_locks_catalog_ownership_and_non_ownership():
    definition = load_json("skill-task.json")
    boundary = definition["authority_boundary"]

    assert boundary["catalog_owns"] == [
        "category tree",
        "attribute templates",
        "admission rules",
        "operating targets",
        "category strategy and lifecycle decision record",
    ]
    assert boundary["catalog_does_not_own_or_write"] == [
        "merchant facts",
        "assortment-wave facts",
        "listing facts",
        "inventory facts",
        "promotion facts",
        "quality facts",
        "supply-chain facts",
        "BI facts",
    ]
    assert not any("capability_id" in step for step in definition["steps"])
    assert not any(step.get("operation_type") == "WRITE" for step in definition["steps"])


def test_e2e_sop_covers_all_lifecycle_controls_without_fake_execution():
    definition = load_json("skill-task.json")
    steps = definition["steps"]

    assert [step["step_order"] for step in steps] == list(range(1, 10))
    assert [step["step_code"] for step in steps] == [
        "define_category_scope_and_targets",
        "diagnose_category_and_identify_opportunities",
        "decide_planning_and_supply_portfolio",
        "approve_controlled_domain_handoffs",
        "monitor_execution_readbacks",
        "conduct_periodic_category_review",
        "execute_approved_remediation",
        "approve_upgrade_or_maintain",
        "approve_downgrade_or_exit",
    ]
    assert all(step["step_kind"] == "MANUAL_EVIDENCE_GATE" for step in steps)
    assert all(step["responsible"] for step in steps)
    assert all(step["required_inputs"] for step in steps)
    assert all(step["required_evidence"] for step in steps)
    assert definition["state_machine"]["terminal"] == ["ACTIVE", "EXITED"]
    assert "Outbox event" in definition["idempotency_policy"]["outbox_policy"]
    assert "No runnable category-management query is registered" in definition["readback_requirement"]


def test_guide_preserves_boundaries_and_human_decision_rule():
    guide = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    for text in (
        "Catalog/商品域新增的业务角色级 **品类管理** SOP",
        "`cloudmold-category-daily-operations` 保留原名和职责",
        "`cloudmold-assortment-planning-lifecycle` 仍拥有商品企划波段",
        "它不直写 Merchant、Assortment、Listing、Inventory、Promotion、Quality、Supply Chain 或 BI",
        "AI 只能产生带来源、时间窗、版本和不确定性的建议",
        "幂等键",
        "版本化 Outbox",
        "local/test/demo",
        "生产证据",
    ):
        assert text in guide


def test_references_lock_the_confirmed_operating_model_and_guardrails():
    lifecycle = (ROOT / "references" / "lifecycle-sop.md").read_text(encoding="utf-8")
    rules = (ROOT / "references" / "rules-and-calculations.md").read_text(encoding="utf-8")

    for text in (
        "L1 战略层",
        "L2 计划层",
        "L3 执行层",
        "L4 保障层",
        "Quality 与 Supply Chain 对质量安全、入仓和履约风险具有**阻断/升级权**",
        "T-16~T-13",
        "T-14~T-10",
        "T-12~T-9",
        "T-10~T-7",
        "T-8~T-5",
        "T-4~T-1",
        "每月首个工作日月度品类会",
        "每季度季度准入评审",
        "每周三爆品评审会",
        "每周招商进度会",
    ):
        assert text in lifecycle

    for text in (
        "Top10 品牌 GMV 占比 **>50%**",
        "叶子类目年 GMV 必须 **>1 亿元**",
        "S `≥60`，A `40~59`，B `<40`",
        "直播与搜索均 `≥30%` 时优先归双驱",
        "每日固定上新 1,300",
        "固定 30 天月度坑位为 39,000",
        "M_t = round(M_(t-1) × 1.10)",
        "高退货 `>60%`：条件准入",
        "强直播依赖（直播 `>30%`）：条件准入",
        "供应商至少 10 家",
        "≥目标坑位×1.5",
        "高潜池占比 `≥40%`",
        "蓬松度 `≥600FP`",
        "含绒量 `≥90%`",
        "真丝含量 `≥95%`",
        "A 类甲醛 `≤20mg/kg`",
        "B 类 `≤75mg/kg`",
        "最低单件贡献毛利率 27%",
        "财务必须先确认“最高入仓供价”是否已含正向入仓 1.76 元",
        "八类人工升级",
    ):
        assert text in rules


def test_report_contract_labels_its_data_assumptions_and_unknowns():
    report = (ROOT / "references" / "report-and-data-contract.md").read_text(encoding="utf-8")

    for text in (
        "准入标记总览",
        "品牌集中度",
        "热力图",
        "渠道分布",
        "发展现状",
        "产地城市招商指引",
        "优先级矩阵",
        "专项分析",
        "月度坑位规划",
        "七张核心数据表草案（未落地）",
        "品类策略与决策台账",
        "BI 交易识别、分区安全、均值、冬季 GMV、BCA 合并规则",
        "完整 13 类特殊场景词典",
    ):
        assert text in report


def test_escalation_rules_remain_human_owned_and_time_bounded():
    rules = (ROOT / "references" / "rules-and-calculations.md").read_text(encoding="utf-8")

    for text in (
        "QC 合格率连续 3 周 `<90%`",
        "爆款率环比下降 `≥10pp`",
        "供应商履约率 `<80%`",
        "大促期 GMV 连续 3 日低于计划 50%",
        "新品类准入争议",
        "坑位分配争议",
        "供给储备不足",
        "48h",
        "72h",
        "24h",
        "1 周",
        "Agent 不得自行开关",
        "不可直接写坑位",
    ):
        assert text in rules
