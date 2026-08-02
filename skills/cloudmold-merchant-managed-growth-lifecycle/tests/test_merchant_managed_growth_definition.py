import json
from pathlib import Path


SKILL_ROOT = Path(__file__).parents[1]


def test_managed_growth_lifecycle_is_evidence_gated_and_registered():
    definition = json.loads((SKILL_ROOT / "skill-task.json").read_text(encoding="utf-8"))
    manifest = json.loads((SKILL_ROOT / "skill.json").read_text(encoding="utf-8"))

    assert definition["skill_id"] == "skill.cloudmold.merchant.managed-growth-lifecycle.v1"
    assert definition["workflow_level"] == "BUSINESS_ROLE"
    assert definition["owner_role"] == "merchant-managed-growth-operator"
    assert definition["risk_level"] == "R3"
    assert [step["step_order"] for step in definition["steps"]] == list(range(1, 15))
    assert manifest["authority"] == "manual-evidence-gated"

    writes = [step for step in definition["steps"] if step.get("operation_type") == "WRITE"]
    assert len(writes) == 13
    assert all(step["approval_required"] for step in writes)
    assert all("idempotency_binding" in step for step in writes)
    assert {step["capability_id"] for step in writes} == {
        "capability.cloudmold.merchant.merchant-command.execute.v1"
    }

    by_code = {step["step_code"]: step for step in definition["steps"]}
    assert by_code["accept_ai_diagnostic"]["arguments"][0]["$overrides"]["operation"] == "ACCEPT_AI_DIAGNOSTIC"
    assert by_code["create_factory_inspection_task"]["arguments"][0]["$overrides"]["operation"] == (
        "CREATE_FACTORY_INSPECTION_TASK"
    )
    assert by_code["record_managed_final_review"]["arguments"][0]["$overrides"]["operation"] == (
        "RECORD_MANAGED_FINAL_REVIEW"
    )
    assert by_code["complete_factory_inspection_task"]["arguments"][0]["$overrides"]["operation"] == (
        "COMPLETE_FACTORY_INSPECTION_TASK"
    )
    terminal = by_code["verify_managed_growth_terminal"]
    assert terminal["step_kind"] == "WAIT_CAPABILITY"
    assert terminal["capability_id"] == (
        "capability.cloudmold.merchant.merchant-managed-admission-workflow-query.inspect.v1"
    )
    assert terminal["wait_success"] == {"/status": "SUCCEEDED"}
    assert terminal["wait_failure"] == {"/status": ["FAILED"]}


def test_managed_growth_skill_locks_the_confirmed_business_rules():
    guide = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for required_text in (
        "新商入驻六阶段",
        "唯一",
        "人工通过",
        "补齐信息",
        "不可流转",
        "转买手 TL",
        "自营或托管大店",
        "已对接 Merchant red-zone 中**已落地**的托管准入后端 happy path",
        "业务规则要求创建一条受控验厂任务",
        "验厂小二认领和执行",
        "待认领 → 待预约验厂 → 待验厂 → 待 QA 验厂 → 待整改 → 待一审 → 待终审 → 验厂完成",
        "任一非终态均可取消",
        "当前 SkillTask 只覆盖“**AI 建议已被人工接受且进入验厂链路**”的受控直行路径",
        "通过已注册的 Merchant managed-admission workflow query 只读回查终态",
        "综合评分、以下五项分项评分、问题清单、逐项整改要求及其证据",
        "商品开发",
        "视觉素材",
        "生产及供应链",
        "质量管理",
        "仓储物流",
        "高风险或硬性不通过项必须直接阻断通过或进入整改/复验",
        "验厂等级为 **C 级及以上**",
        "劣质图比例 **<10%**",
        "尺码覆盖度 **>80%**",
        "问题订单率 = 问题订单 / 同期有效订单",
        "S/A 企划匹配覆盖度 **≥80%**",
        "等级跃迁",
        "坑位上新数",
        "重点供应商候选",
        "退出托管池及相关权益",
    ):
        assert required_text in guide

    assert "不得将上述月度综合能力评分或等级跃迁写成“月签”" in guide
    assert "首期仍**不**自动生成邀请码或入驻链接" in guide
    assert "不是后台自动派单" in guide
    assert "已注册的 Merchant managed-admission workflow query 只读回查终态" in guide
    assert "终态只读回查目前仅覆盖 Merchant managed-admission workflow 已公开的 `SUCCEEDED/FAILED` 结果" in guide
    assert "邀请码使用、买手分配、等级/权益决定、试用/成长期评分和托管池退出" in guide


def test_monthly_growth_obligations_have_configured_evidence_and_decision_rules():
    guide = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    growth_section = guide.split("## 4. 成长期：月度九项义务、评分与权益", 1)[1].split(
        "## 5. 清退与整改边界", 1
    )[0]

    obligations = (
        "无货源风险控制",
        "企划匹配供给",
        "商品发货质量",
        "稳定供应链",
        "版房与打样",
        "月度坑位履约",
        "经营动销",
        "核价配合",
        "品质监控",
    )
    headers = [f"### 4.{index} {obligation}" for index, obligation in enumerate(obligations, 1)]
    for index, header in enumerate(headers):
        entry = growth_section.split(header, 1)[1]
        if index + 1 < len(headers):
            entry = entry.split(headers[index + 1], 1)[0]
        for label in ("**义务项**", "**考核内容**", "**达标标准**", "**对应权益**", "**等级跃迁**"):
            assert label in entry

    assert "商家等级、类目和企划等级等规则配置" in growth_section
    assert "升级、维持或降级" in growth_section
    assert "权益只在当月对应义务持续满足时生效" in growth_section
    assert "不得使用“稳定率”" in growth_section
