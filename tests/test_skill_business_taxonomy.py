"""Contract checks for the business-unit/domain/role skill taxonomy."""

import json
import unittest
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
TAXONOMY_PATH = SKILLS_ROOT / "business-taxonomy.json"


class SkillBusinessTaxonomyTest(unittest.TestCase):

    def setUp(self):
        self.taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

    def test_taxonomy_exposes_business_unit_domain_role_hierarchy(self):
        self.assertEqual(
            "cloudmold.skill-business-taxonomy/v1",
            self.taxonomy["schema_version"],
        )
        units = {item["code"]: item for item in self.taxonomy["business_units"]}
        domains = {item["code"]: item for item in self.taxonomy["domains"]}
        roles = {item["code"]: item for item in self.taxonomy["roles"]}

        self.assertEqual("得物", units["dewu"]["name"])
        self.assertEqual("Fashion88", units["fashion88"]["name"])
        self.assertEqual("ACTIVE", units["dewu"]["status"])
        self.assertEqual("PLANNED", units["fashion88"]["status"])
        self.assertTrue(
            {
                "merchant",
                "supply-chain",
                "quality",
                "product",
                "pricing",
                "user",
                "experience",
                "merchant-acquisition",
            }.issubset(domains)
        )
        self.assertTrue(all(role["domain_code"] in domains for role in roles.values()))

    def test_every_business_role_has_one_dewu_assignment_and_runnable_skill(self):
        assignments = self.taxonomy["skill_assignments"]
        assignments_by_role = {}
        for assignment in assignments:
            assignments_by_role.setdefault(assignment["role_code"], []).append(assignment)

        definitions = []
        for path in SKILLS_ROOT.glob("*/skill-task.json"):
            definition = json.loads(path.read_text(encoding="utf-8"))
            if definition.get("workflow_level") == "BUSINESS_ROLE":
                definitions.append((path, definition))

        self.assertEqual(35, len(definitions))
        for task_path, definition in definitions:
            role_code = definition["owner_role"]
            with self.subTest(role_code=role_code):
                matches = assignments_by_role.get(role_code, [])
                self.assertEqual(1, len(matches))
                assignment = matches[0]
                self.assertEqual("dewu", assignment["business_unit_code"])
                self.assertEqual(task_path.parent.name, assignment["skill_name"])
                self.assertTrue((task_path.parent / "SKILL.md").is_file())

    def test_assignments_reference_existing_taxonomy_nodes_and_skill_packages(self):
        unit_codes = {item["code"] for item in self.taxonomy["business_units"]}
        role_codes = {item["code"] for item in self.taxonomy["roles"]}
        seen = set()

        for assignment in self.taxonomy["skill_assignments"]:
            key = (
                assignment["business_unit_code"],
                assignment["role_code"],
                assignment["skill_name"],
            )
            with self.subTest(key=key):
                self.assertNotIn(key, seen)
                seen.add(key)
                self.assertIn(assignment["business_unit_code"], unit_codes)
                self.assertIn(assignment["role_code"], role_codes)
                self.assertTrue(
                    (SKILLS_ROOT / assignment["skill_name"] / "SKILL.md").is_file()
                )


if __name__ == "__main__":
    unittest.main()
