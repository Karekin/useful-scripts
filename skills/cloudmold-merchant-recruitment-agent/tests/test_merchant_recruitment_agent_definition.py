import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_recruitment_agent_skill_is_governed_and_documents_all_four_nodes():
    manifest = json.loads((ROOT / "skill.json").read_text(encoding="utf-8"))
    guide = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert manifest["skill_id"] == "skill.cloudmold.merchant.recruitment-agent.v1"
    assert manifest["authority"] == "manual-evidence-gated"
    assert manifest["risk_level"] == "R3"
    for heading in ("## 1. 线索挖掘", "## 2. 商家建联", "## 3. 商机转化", "## 4. 入驻引导"):
        assert heading in guide


def test_recruitment_agent_locks_ai_rpa_and_human_boundaries():
    guide = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    for required_text in (
        "每日 20 人",
        "不得绕过 API 限流",
        "字段级操作授权",
        "不得猜测或代填",
        "AI 不单独作出正式准入结论",
        "买手接收确认后进入 `已交接`",
        "不得在商家拒绝、投诉或免打扰后继续自动触达",
        "约 **1,300** 条入库线索",
        "约 **65** 个",
    ):
        assert required_text in guide


def test_recruitment_agent_has_default_implementations_for_each_module():
    guide = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "## 7. 默认实现蓝图" in guide
    for section in (
        "### 7.2 线索挖掘默认实现",
        "### 7.3 商家建联默认实现",
        "### 7.4 商机转化默认实现",
        "### 7.5 入驻引导默认实现",
    ):
        assert section in guide
    for module in (
        "线索引入",
        "线索评分",
        "线索交付",
        "线索分配",
        "自动建联",
        "资格判定",
        "商家入群",
        "群聊全托管",
        "商家档案管理",
        "商机判断",
        "辅助填写入驻信息",
        "辅助商家入驻审核",
        "辅助商家提交货盘",
        "对接买手",
    ):
        assert module in guide
