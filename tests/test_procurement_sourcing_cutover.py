import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProcurementSourcingCutoverTest(unittest.TestCase):

    def test_registry_and_demo_configuration_have_no_retired_sourcing_contract(self):
        roots = [ROOT / "skills", ROOT / "yml" / "yudao" / "docker-compose.yaml"]
        content = []
        for root in roots:
            paths = [root] if root.is_file() else root.rglob("*")
            for path in paths:
                if path.is_file() and path.suffix in {".json", ".md", ".yaml", ".yml"}:
                    content.append(path.read_text(encoding="utf-8"))
        material = "\n".join(content)
        forbidden = [
            "skill.cloudmold." + "supplier.sourcing",
            "Supplier" + "Sourcing",
            "supplier" + "_ref",
            "supplier" + "Ref",
            "supplier-" + "sourcing",
            "supplier_" + "sourcing",
            "cloudmold-" + "supplier-" + "sourcing",
            "RELEASE_AWARD" + "_TO_PURCHASE_ORDERS",
        ]
        for token in forbidden:
            self.assertNotIn(token, material, token)

        self.assertIn("skill.cloudmold.procurement.sourcing-lifecycle.v1", material)
        self.assertIn("skill.cloudmold.procurement.sourcing-decision-readback.v1", material)
        self.assertIn("capability.cloudmold.procurement.sourcing-query.require-award.v1", material)


if __name__ == "__main__":
    unittest.main()
