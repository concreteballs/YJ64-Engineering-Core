import json
import unittest

from yj64_engineering_core.task_contracts import TaskRequest


class TaskRequestContractTests(unittest.TestCase):
    def make_request(self):
        return TaskRequest(
            task_id="repo-review-001",
            task_type="code.review",
            title="Review repository",
            objective="Find correctness and security issues",
            input_data={"repository": "owner/project", "ref": "main"},
            constraints={"read_only": True},
            requested_capabilities=("github.read", "python.test"),
            council_policy="optional",
            approval_policy={"write_changes": "human_required"},
        )

    def test_json_round_trip(self):
        request = self.make_request()
        restored = TaskRequest.from_json(request.to_json())
        self.assertEqual(restored, request)
        self.assertEqual(json.loads(request.to_json())["contract_version"], "1.0")

    def test_accepts_different_task_domains(self):
        for task_type in ("code.review", "engineering.analysis", "research", "browser.audit"):
            with self.subTest(task_type=task_type):
                request = TaskRequest(
                    task_id="task-1", task_type=task_type,
                    title="Task", objective="Do work",
                )
                self.assertEqual(request.task_type, task_type)

    def test_rejects_invalid_task_type(self):
        with self.assertRaises(ValueError):
            TaskRequest(
                task_id="task-1", task_type="Code Review",
                title="Task", objective="Do work",
            )

    def test_rejects_unknown_council_policy(self):
        with self.assertRaises(ValueError):
            TaskRequest(
                task_id="task-1", task_type="code.review",
                title="Task", objective="Do work", council_policy="automatic",
            )

    def test_rejects_non_finite_nested_values(self):
        with self.assertRaises(ValueError):
            TaskRequest(
                task_id="task-1", task_type="engineering.analysis",
                title="Task", objective="Do work",
                input_data={"nested": [float("nan")]},
            )

    def test_rejects_non_json_values(self):
        with self.assertRaises(TypeError):
            TaskRequest(
                task_id="task-1", task_type="code.review",
                title="Task", objective="Do work",
                input_data={"bad": object()},
            )

    def test_rejects_oversized_envelope(self):
        with self.assertRaisesRegex(ValueError, "256 KiB"):
            TaskRequest(
                task_id="task-1", task_type="research",
                title="Task", objective="Do work",
                input_data={"text": "x" * (256 * 1024)},
            )

    def test_rejects_json_nan_constant(self):
        with self.assertRaises(ValueError):
            TaskRequest.from_json(
                '{"task_id":"task-1","task_type":"research","title":"T",'
                '"objective":"O","input_data":{"value":NaN}}'
            )


if __name__ == "__main__":
    unittest.main()
