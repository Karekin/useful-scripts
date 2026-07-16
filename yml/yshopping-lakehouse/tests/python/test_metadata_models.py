import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))
ORDER = [
    line.strip()
    for line in (ROOT / "models/apply-order-v1.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]


class MetadataModelsTest(unittest.TestCase):
    EVENTS = {
        "metadata.datasource.version_published", "metadata.dataset.version_published",
        "metadata.dataset_field.version_published", "metadata.task.version_published",
        "metadata.task_dependency.version_published", "metadata.task_run.observed",
        "metadata.lineage.version_published", "metadata.dqc_rule.version_published",
        "metadata.dqc_result.recorded", "metadata.metric.version_published",
    }

    def test_all_backend_events_are_strict_and_exactly_manifested(self):
        self.assertTrue(self.EVENTS.issubset(MANIFEST["events"]))
        for event_type in self.EVENTS:
            config = MANIFEST["events"][event_type]
            schema = json.loads((ROOT / "contracts" / config["payload_schema"]).read_text(encoding="utf-8"))
            self.assertFalse(schema["additionalProperties"], event_type)
            self.assertEqual(set(schema["required"]), set(schema["properties"]), event_type)

    def test_raw_sql_connections_and_credentials_are_not_payload_fields(self):
        forbidden = {"url", "username", "password", "credential", "raw_sql", "sql_content", "raw_error"}
        for event_type in self.EVENTS:
            schema_path = ROOT / "contracts" / MANIFEST["events"][event_type]["payload_schema"]
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertTrue(forbidden.isdisjoint(schema["properties"]), event_type)

    def test_field_and_dependency_detail_are_replayable(self):
        field = MANIFEST["events"]["metadata.dataset_field.version_published"]
        field_schema = json.loads((ROOT / "contracts" / field["payload_schema"]).read_text(encoding="utf-8"))
        self.assertTrue({"dataset_id", "dataset_version", "ordinal_position", "field_code", "data_type",
                         "nullable", "primary_key_part", "semantic_type", "classification"}
                        .issubset(field_schema["required"]))
        dependency = MANIFEST["events"]["metadata.task_dependency.version_published"]
        dependency_schema = json.loads(
            (ROOT / "contracts" / dependency["payload_schema"]).read_text(encoding="utf-8")
        )
        self.assertTrue({"task_id", "task_version", "dependency_sequence", "upstream_task_id",
                         "upstream_task_version", "dependency_type", "required"}
                        .issubset(dependency_schema["required"]))

    def test_model_dependency_order_and_history_policy(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        dwd = "models/dwd/dwd-canonical-metadata-event.sql"
        dim = "models/dim/dim-canonical-metadata-current.sql"
        dws = "models/dws/dws-canonical-metadata-current.sql"
        ads = "models/ads/ads-canonical-metadata-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
        self.assertLess(positions[dwd], positions[dim])
        self.assertLess(positions[dim], positions[dws])
        self.assertLess(positions[dws], positions[ads])
        dim_sql = (ROOT / dim).read_text(encoding="utf-8")
        for history in ("datasource_version_history", "dataset_version_history", "dataset_field_version_history",
                        "task_version_history", "task_dependency_version_history", "lineage_version_history",
                        "dqc_rule_version_history", "metric_version_history", "task_run_observation_history",
                        "dqc_result_history"):
            self.assertIn(history, dim_sql)

    def test_dqc_locks_exact_versions_sequences_graph_and_privacy(self):
        dqc = (ROOT / "tests/sql/26-canonical-metadata-contract.sql").read_text(encoding="utf-8")
        for check in (
            "metadata_event_payload_sensitive_material_leak", "metadata_definition_version_sequence_gap",
            "metadata_dataset_field_count_mismatch", "metadata_dataset_field_ordinal_invalid",
            "metadata_dqc_dataset_field_reference_invalid", "metadata_task_dependency_count_mismatch",
            "metadata_task_dependency_endpoint_invalid", "metadata_task_dependency_direct_edge_duplicate",
            "metadata_task_dependency_self_loop", "metadata_lineage_two_edge_cycle",
            "metadata_task_run_sequence_gap_or_task_version_invalid", "metadata_task_run_transition_invalid",
            "metadata_task_run_measurement_or_iso_currency_invalid", "metadata_dqc_exact_reference_invalid",
            "metadata_unproven_completion_flag",
        ):
            self.assertIn(check, dqc)
        self.assertIn("field.aggregate_version <> field.dataset_version", dqc)
        self.assertIn("dependency.aggregate_version <> dependency.task_version", dqc)
        self.assertIn("current_status NOT IN ('RUNNING','CANCELLED')", dqc)
        self.assertIn("current_status NOT IN ('SUCCEEDED','FAILED','CANCELLED')", dqc)
        self.assertIn("TIMESTAMPDIFF(MILLISECOND, started_at, finished_at) <> duration_millis", dqc)
        self.assertIn("exact_dataset_field_inventory_replayable = false", dqc)

    def test_readiness_is_derived_but_remains_honestly_partial(self):
        ads = (ROOT / "models/ads/ads-canonical-metadata-readiness.sql").read_text(encoding="utf-8")
        self.assertIn("dataset_field_inventory_replayable", ads)
        self.assertIn("direct_task_dependency_graph_replayable", ads)
        self.assertIn("false AS task_dependency_graph_replayable", ads)
        self.assertIn("false AS transitive_dag_runtime_verified", ads)
        self.assertIn("OR exact_dataset_field_inventory_replayable = false", ads)
        self.assertIn("FIRST_SLICE_PARTIAL", ads)
        self.assertIn("nonempty_runtime_reconciled", ads)
        alignment = json.loads((ROOT / "contracts/yshopping-model-alignment-v1.json").read_text(encoding="utf-8"))
        metadata = next(unit for unit in alignment["alignment_units"] if unit["id"] == "metadata")
        self.assertEqual("partial", metadata["backend"]["status"])
        self.assertEqual("partial", metadata["lakehouse"]["status"])
        self.assertTrue(metadata["backend"]["gaps"])
        self.assertTrue(metadata["lakehouse"]["gaps"])


if __name__ == "__main__":
    unittest.main()
