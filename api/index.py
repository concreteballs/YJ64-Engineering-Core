"""Authenticated, persistent ingress for YJ64 GitHub Actions completion events.

POST /api validates the CI event, persists it in PostgreSQL and enqueues an
idempotent process_ci_event task. A separate worker must claim and process
that task; this endpoint does not run model inference or repository code.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore  # noqa: E402


EXPECTED_REPOSITORY = "concreteballs/YJ64-Engineering-Core"
EXPECTED_BRANCH = "main"
EXPECTED_EVENT = "yj64.ci.completed"
MAX_BODY_BYTES = 16 * 1024


def _database_sqlstate(exc: Exception) -> str | None:
    """Return a validated SQLSTATE from psycopg 3 or psycopg2 exceptions."""
    for attribute in ("sqlstate", "pgcode"):
        value = getattr(exc, attribute, None)
        if isinstance(value, str) and re.fullmatch(r"[0-9A-Z]{5}", value):
            return value
    return None


def _safe_database_error_code(exc: Exception) -> str:
    """Classify database failures without exposing exception text or secrets."""
    sqlstate = _database_sqlstate(exc)
    if sqlstate:
        # SQLSTATE class codes are more reliable than broad Python exception names.
        if sqlstate.startswith("08"):
            return "database_connection_error"
        if sqlstate.startswith("28"):
            return "database_authentication_error"
        if sqlstate.startswith("23"):
            return "database_integrity_error"
        if sqlstate.startswith("42") or sqlstate.startswith("3D"):
            return "database_schema_error"
        if sqlstate == "42501":
            return "database_permission_error"
        if sqlstate.startswith("0A"):
            return "database_feature_error"
        return "database_sqlstate_" + sqlstate

    name = type(exc).__name__
    if name in {"OperationalError", "InterfaceError"}:
        return "database_connection_error"
    if name in {"ProgrammingError", "UndefinedTable", "UndefinedColumn"}:
        return "database_schema_error"
    if name in {"IntegrityError", "UniqueViolation", "CheckViolation"}:
        return "database_integrity_error"
    if name in {"ImportError", "ModuleNotFoundError"}:
        return "database_driver_error"
    return "database_operation_error"


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
        configured = bool(
            os.environ.get("YJ64_DATABASE_URL") or os.environ.get("DATABASE_URL")
        )
        self._send_json(
            200,
            {
                "ok": True,
                "service": "yj64-ci-webhook-ingress",
                "mode": "postgres_persistent_queue" if configured else "not_configured",
                "persistence_configured": configured,
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
        if not hmac.compare_digest(supplied, "Bearer " + secret):
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
            "event", "repository", "workflow", "run_id", "run_attempt",
            "conclusion", "commit_sha", "branch", "run_url",
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
        valid_conclusions = {
            "success", "failure", "cancelled", "timed_out",
            "action_required", "neutral", "skipped", "stale",
        }
        if (
            not isinstance(payload["conclusion"], str)
            or payload["conclusion"] not in valid_conclusions
        ):
            self._send_json(422, {"ok": False, "error": "invalid_conclusion"})
            return
        run_url = payload["run_url"]
        expected_prefix = (
            "https://github.com/" + EXPECTED_REPOSITORY + "/actions/runs/"
        )
        if (
            not isinstance(run_url, str)
            or not run_url.startswith(expected_prefix)
            or not run_url[len(expected_prefix):].split("/", 1)[0].isdigit()
        ):
            self._send_json(422, {"ok": False, "error": "invalid_run_url"})
            return

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
        database_url = os.environ.get("YJ64_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not database_url:
            self._send_json(503, {"ok": False, "error": "database_not_configured"})
            return
        try:
            result = PostgresCycleStore(database_url).record_ci_event(event_record)
        except Exception as exc:
            # Return only a fixed category; never expose exception text or connection data.
            self._send_json(
                503,
                {"ok": False, "error": "persistent_queue_unavailable",
                 "diagnostic": _safe_database_error_code(exc),
                 "sqlstate": _database_sqlstate(exc)},
            )
            return
        self._send_json(
            202,
            {
                "ok": True,
                "accepted": True,
                "duplicate": result["duplicate"],
                "event_id": result["event_id"],
                "task_enqueued": result["task_enqueued"],
                "mode": "postgres_persistent_queue",
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        return
