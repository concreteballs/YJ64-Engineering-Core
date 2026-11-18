import unittest
from pathlib import Path
from runpy import run_path
from unittest.mock import patch


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_ci_patch_generation_worker.py"
_publish_candidate = run_path(str(_SCRIPT))["publish_candidate_for_review"]


class CiPatchHumanReviewPublisherTests(unittest.TestCase):
    def test_refuses_candidate_without_human_review_gate(self):
        candidate = {
            "candidate_status": "awaiting_review",
            "safety": {
                "git_apply_check": True,
                "human_approval_required": True,
                "auto_apply": True,
                "auto_commit": False,
            },
            "patch": {"unified_diff": "--- a/a.py\n+++ b/a.py\n", "target_files": ["a.py"]},
            "source": {"current_head_sha": "a" * 40},
            "proposal_task_id": 1,
            "candidate_sha256": "b" * 64,
        }
        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "candidate_not_eligible_for_human_review"):
                _publish_candidate(
                    candidate,
                    repository="concreteballs/YJ64-Engineering-Core",
                    token="test-token",
                )
            run.assert_not_called()

    def test_rejects_diff_file_headers_mismatch_before_git(self):
        candidate = {
            "candidate_status": "awaiting_review",
            "safety": {
                "git_apply_check": True,
                "human_approval_required": True,
                "auto_apply": False,
                "auto_commit": False,
            },
            "patch": {
                "unified_diff": "--- a/allowed.py\\n+++ b/allowed.py\\n@@ -1 +1 @@\\n-old\\n+new\\n",
                "target_files": ["other.py"],
            },
            "source": {"current_head_sha": "a" * 40},
            "proposal_task_id": 1,
            "candidate_sha256": "b" * 64,
        }
        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "patch_review_diff_file_set_mismatch"):
                _publish_candidate(
                    candidate,
                    repository="concreteballs/YJ64-Engineering-Core",
                    token="test-token",
                )
            run.assert_not_called()

    def test_rejects_traversal_in_declared_files_before_git(self):
        candidate = {
            "candidate_status": "awaiting_review",
            "safety": {
                "git_apply_check": True,
                "human_approval_required": True,
                "auto_apply": False,
                "auto_commit": False,
            },
            "patch": {
                "unified_diff": "--- a/../escape.py\\n+++ b/../escape.py\\n@@ -1 +1 @@\\n-old\\n+new\\n",
                "target_files": ["../escape.py"],
            },
            "source": {"current_head_sha": "a" * 40},
            "proposal_task_id": 1,
            "candidate_sha256": "b" * 64,
        }
        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "patch_review_candidate_invalid"):
                _publish_candidate(
                    candidate,
                    repository="concreteballs/YJ64-Engineering-Core",
                    token="test-token",
                )
            run.assert_not_called()

    def test_refuses_unexpected_repository_before_git_access(self):
        candidate = {}
        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "patch_review_repository_rejected"):
                _publish_candidate(candidate, repository="attacker/repo", token="test-token")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
