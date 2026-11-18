import json
import unittest

from yj64_engineering_core.automation.ci_patch_generation import (
    extract_candidate_paths,
    parse_patch_response,
)


class CiPatchGenerationTests(unittest.TestCase):
    def test_extracts_only_explicit_repository_paths(self):
        report = {
            "summary": "Python tests failed in tests/test_worker.py",
            "root_cause": "FakeStore method signature mismatch",
            "evidence": [{
                "log_excerpt": 'File "/home/runner/work/YJ64-Engineering-Core/YJ64-Engineering-Core/src/yj64_engineering_core/automation/worker.py", line 42',
                "interpretation": "The production worker called the method with a keyword argument.",
            }],
            "suggested_actions": ["Update tests/test_worker.py"],
            "verification_steps": [],
            "risk_notes": [],
        }
        paths = extract_candidate_paths(report, "concreteballs/YJ64-Engineering-Core")
        self.assertEqual(paths, [
            "src/yj64_engineering_core/automation/worker.py",
            "tests/test_worker.py",
        ])

    def test_does_not_guess_paths_when_evidence_has_none(self):
        report = {
            "summary": "Build failed",
            "root_cause": "Dependency resolution failed",
            "evidence": [],
            "suggested_actions": ["Check the package registry."],
            "verification_steps": [],
            "risk_notes": [],
        }
        self.assertEqual(extract_candidate_paths(report, "concreteballs/YJ64-Engineering-Core"), [])

    def _response(self, diff, paths):
        return json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": json.dumps({
                    "summary": "Minimal test fix",
                    "unified_diff": diff,
                    "target_files": paths,
                    "verification_steps": ["Run focused tests."],
                    "confidence": 0.82,
                })}]}
            }]
        }).encode()

    def test_accepts_patch_only_for_inspected_files(self):
        diff = (
            "diff --git a/tests/test_worker.py b/tests/test_worker.py\n"
            "--- a/tests/test_worker.py\n"
            "+++ b/tests/test_worker.py\n"
            "@@ -1 +1 @@\n"
            "-old\n+new\n"
        )
        parsed, error = parse_patch_response(self._response(diff, ["tests/test_worker.py"]), {"tests/test_worker.py"})
        self.assertIsNone(error)
        self.assertEqual(parsed["target_files"], ["tests/test_worker.py"])

    def test_rejects_patch_touching_uninspected_file(self):
        diff = (
            "--- a/src/secret.py\n"
            "+++ b/src/secret.py\n"
            "@@ -1 +1 @@\n"
            "-old\n+new\n"
        )
        parsed, error = parse_patch_response(self._response(diff, ["src/secret.py"]), {"tests/test_worker.py"})
        self.assertIsNone(parsed)
        self.assertEqual(error, "patch_touches_uninspected_file")

    def test_rejects_path_traversal_and_file_deletion(self):
        traversal = (
            "--- a/../secret.py\n"
            "+++ b/../secret.py\n"
            "@@ -1 +1 @@\n"
            "-old\n+new\n"
        )
        parsed, error = parse_patch_response(self._response(traversal, ["../secret.py"]), {"../secret.py"})
        self.assertIsNone(parsed)
        self.assertEqual(error, "patch_path_unsafe")

        deletion = (
            "--- a/tests/test_worker.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-old\n"
        )
        parsed, error = parse_patch_response(self._response(deletion, ["tests/test_worker.py"]), {"tests/test_worker.py"})
        self.assertIsNone(parsed)
        self.assertEqual(error, "patch_file_headers_invalid")


if __name__ == "__main__":
    unittest.main()
