import unittest
from datetime import datetime, timezone

from yj64_engineering_core.automation.checkpoints import (
    create_checkpoint,
    verify_checkpoint,
)


class CheckpointContractTests(unittest.TestCase):
    def make_checkpoint(self):
        return create_checkpoint(
            task_id="task-01",
            sequence=1,
            state="running",
            task_spec_version="1",
            task_state={"stage": "analysis", "completed": [], "pending": ["step-1"]},
            budgets={"tokens": 10000, "cost_usd": 2.0, "time_seconds": 300},
            approvals={"external_network": False},
            artifact_refs=["sha256:artifact-a"],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_checkpoint_has_stable_hash(self):
        first = self.make_checkpoint()
        second = self.make_checkpoint()
        self.assertEqual(first, second)
        self.assertTrue(verify_checkpoint(first))

    def test_hash_detects_payload_mutation(self):
        checkpoint = self.make_checkpoint()
        checkpoint["task_state"]["stage"] = "execution"
        with self.assertRaisesRegex(ValueError, "integrity"):
            verify_checkpoint(checkpoint)

    def test_rejects_boolean_sequence(self):
        with self.assertRaises(ValueError):
            create_checkpoint(
                task_id="task-01", sequence=True, state="running",
                task_spec_version="1", task_state={}, budgets={}, approvals={}
            )

    def test_rejects_naive_timestamp(self):
        with self.assertRaises(ValueError):
            create_checkpoint(
                task_id="task-01", sequence=1, state="running",
                task_spec_version="1", task_state={}, budgets={}, approvals={},
                created_at=datetime(2026, 1, 1),
            )

    def test_rejects_non_finite_numbers(self):
        with self.assertRaises(ValueError):
            create_checkpoint(
                task_id="task-01", sequence=1, state="running",
                task_spec_version="1", task_state={"bad": float("nan")},
                budgets={}, approvals={}
            )

    def test_rejects_unknown_state(self):
        with self.assertRaises(ValueError):
            create_checkpoint(
                task_id="task-01", sequence=1, state="unknown",
                task_spec_version="1", task_state={}, budgets={}, approvals={}
            )


if __name__ == "__main__":
    unittest.main()
