"""Minimal authenticated ingress for YJ64 GitHub Actions completion events.

This endpoint validates and logs events only. It deliberately does not claim
durable storage, deduplication, or notification delivery; those require a
configured persistence/notification service.
"""

from __future__ import annotations

import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse


EXPECTED_REPOSITORY = "concreteballs/YJ64-Engineering-Core"
EXPECTED_BRANCH = "main"
EXPECTED_EVENT = "yj64.ci.completed"
MAX_BODY_BYTES = 16 * 1024


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path != "/api":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self._send_json(
            200,
            {
                "ok": True,
                "service": "yj64-ci-webhook-ingress",
                "mode": "validation-only",
            },
        )

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        secret = os.environ.get("YJ64_CI_WEBHOOK_SECRET", "")
        if not secret:
            self._send_json(503, {"ok": False, "error": "webhook_not_configured"})
            return

        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + secret
        if not hmac.compare_digest(supplied, expected):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        raw_length = self.headers.get("Content-Length", "")
        try:
            body_length = int(raw_length)
        except (TypeError, ValueError):
            self._send_json(411, {"ok": False, "error": "content_length_required"})
            return

        if body_length < 1 or body_length > MAX_BODY_BYTES:
            self._send_json(413, {"ok": False, "error": "invalid_body_size"})
            return

        raw_body = self.rfile.read(body_length)
        if len(raw_body) != body_length:
            self._send_json(400, {"ok": False, "error": "incomplete_body"})
            return

        try:
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"ok": False, "error": "json_object_required"})
            return

        required = {
            "event",
            "repository",
            "workflow",
            "run_id",
            "run_attempt",
            "conclusion",
            "commit_sha",
            "branch",
            "run_url",
        }
        if not required.issubset(payload):
            self._send_json(400, {"ok": False, "error": "missing_fields"})
            return

        if (
            payload["event"] != EXPECTED_EVENT
            or payload["repository"] != EXPECTED_REPOSITORY
            or payload["branch"] != EXPECTED_BRANCH
            or payload["workflow"] != "Python tests"
        ):
            self._send_json(422, {"ok": False, "error": "event_scope_rejected"})
            return

        if (
            not isinstance(payload["run_id"], int)
            or isinstance(payload["run_id"], bool)
            or payload["run_id"] <= 0
            or not isinstance(payload["run_attempt"], int)
            or isinstance(payload["run_attempt"], bool)
            or payload["run_attempt"] <= 0
        ):
            self._send_json(422, {"ok": False, "error": "invalid_run_identity"})
            return

        if not isinstance(payload["commit_sha"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", payload["commit_sha"]
        ):
            self._send_json(422, {"ok": False, "error": "invalid_commit_sha"})
            return

        if payload["conclusion"] not in {
            "success",
            "failure",
            "cancelled",
            "timed_out",
            "action_required",
            "neutral",
            "skipped",
            "stale",
        }:
            self._send_json(422, {"ok": False, "error": "invalid_conclusion"})
            return

        run_url = payload["run_url"]
        expected_prefix = (
            "https://github.com/" + EXPECTED_REPOSITORY + "/actions/runs/"
        )
        if (
            not isinstance(run_url, str)
            or not run_url.startswith(expected_prefix)
            or not run_url[len(expected_prefix) :].split("/", 1)[0].isdigit()
        ):
            self._send_json(422, {"ok": False, "error": "invalid_run_url"})
            return

        # Keep logs structured and avoid echoing arbitrary request fields.
        event_record = {
            "event": EXPECTED_EVENT,
            "repository": EXPECTED_REPOSITORY,
            "workflow": "Python tests",
            "run_id": payload["run_id"],
            "run_attempt": payload["run_attempt"],
            "conclusion": payload["conclusion"],
            "commit_sha": payload["commit_sha"],
            "branch": EXPECTED_BRANCH,
            "run_url": run_url,
        }
        print(json.dumps(event_record, separators=(",", ":")))
        self._send_json(
            202,
            {
                "ok": True,
                "accepted": True,
                "mode": "validation-only",
                "run_id": payload["run_id"],
                "run_attempt": payload["run_attempt"],
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        # Avoid logging request headers, which may contain credentials.
        return
