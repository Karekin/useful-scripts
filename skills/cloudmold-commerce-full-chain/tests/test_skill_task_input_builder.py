import importlib.util
import json
import sys
from pathlib import Path
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "build_skill_task_input", SCRIPTS / "build_skill_task_input.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class SkillTaskInputBuilderTest(unittest.TestCase):

    @staticmethod
    def _path(value, expression):
        current = value
        for segment in expression.split("."):
            current = current[int(segment)] if isinstance(current, list) else current[segment]
        return current

    @staticmethod
    def _pointer(value, pointer):
        current = value
        for raw in pointer.removeprefix("/").split("/"):
            segment = raw.replace("~1", "/").replace("~0", "~")
            current = current[int(segment)] if isinstance(current, list) else current[segment]
        return current

    def _assert_override_paths_exist(self, definition, input_value):
        for step in definition["steps"]:
            arguments = step.get("arguments")
            directives = arguments if isinstance(arguments, list) else [arguments]
            for directive in directives:
                if not isinstance(directive, dict) or "$object" not in directive:
                    continue
                base_expression = directive["$object"]
                self.assertTrue(base_expression.startswith("$input."))
                base = self._path(input_value, base_expression.removeprefix("$input."))
                for path in directive["$overrides"]:
                    if path.startswith("/"):
                        self._pointer(base, path)
                    else:
                        self.assertIn(path, base)

    @staticmethod
    def _load_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_builds_all_fixed_child_inputs_with_replaceable_identity_paths(self):
        value = BUILDER.build_input("ai0719r3a01", "1", "3", "2026-07-19T00:00:00Z")

        self.assertEqual(len(value["catalog"]["definitions"]), 6)
        self.assertEqual(len(value["catalog"]["lifecycle"]), 10)
        self.assertEqual(len(value["projection"]["plans"]), 6)
        self.assertEqual(len(value["master"]["merchantCommands"]), 6)
        self.assertEqual(len(value["aftersale"]["commands"]), 25)
        self.assertIn("publisherRef", value["aftersale"]["commands"][5])
        self.assertIn("listingId", value["aftersale"]["commands"][7]["items"][0])
        self.assertIn("reservationId", value["aftersale"]["commands"][12]["items"][0])
        self.assertIn("listingOfferId", value["readback"]["listing"]["validation"])
        self.assertEqual(value["runIds"]["readback"], "ai0719r3a01-readback")

        skill_root = Path(__file__).resolve().parents[2]
        full_chain_skill = self._load_json(skill_root / "cloudmold-commerce-full-chain" / "skill.json")
        full_chain_definition = self._load_json(skill_root / "cloudmold-commerce-full-chain" / "skill-task.json")
        self.assertEqual(full_chain_skill["version"], full_chain_definition["skill_version"])

        definitions = {
            "cloudmold-commerce-full-chain": (value, full_chain_definition),
            "cloudmold-commerce-catalog-matrix": (
                value["catalog"],
                self._load_json(skill_root / "cloudmold-commerce-catalog-matrix" / "skill-task.json"),
            ),
            "cloudmold-commerce-legacy-projection": (
                value["projection"],
                self._load_json(skill_root / "cloudmold-commerce-legacy-projection" / "skill-task.json"),
            ),
            "cloudmold-commerce-reuse-ready-master": (
                value["master"],
                self._load_json(skill_root / "cloudmold-commerce-reuse-ready-master" / "skill-task.json"),
            ),
            "cloudmold-commerce-aftersale-saga": (
                value["aftersale"],
                self._load_json(skill_root / "cloudmold-commerce-aftersale-saga" / "skill-task.json"),
            ),
            "cloudmold-commerce-terminal-readback": (
                value["readback"],
                self._load_json(skill_root / "cloudmold-commerce-terminal-readback" / "skill-task.json"),
            ),
        }
        for input_value, definition in definitions.values():
            self._assert_override_paths_exist(definition, input_value)

        child_versions = {
            step["child_skill_id"]: step["child_skill_version"]
            for step in full_chain_definition["steps"]
            if step.get("step_kind") == "SUBMIT_CHILD"
        }
        self.assertEqual(
            child_versions,
            {
                definition["skill_id"]: definition["skill_version"]
                for _, definition in definitions.values()
                if definition["skill_id"] != full_chain_definition["skill_id"]
            },
        )

    def test_rejects_run_ids_outside_the_governed_shape(self):
        with self.assertRaisesRegex(ValueError, "6-20 characters"):
            BUILDER.build_input("bad id", "1", "3", "2026-07-19T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
