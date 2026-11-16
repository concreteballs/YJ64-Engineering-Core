"""Authenticated agent-facing supplier-discovery planning endpoint.

POST /api/discovery accepts an engineering agent's structured sourcing request.
It validates and expands the request into category/market search tasks.
This endpoint does not execute external searches, persist jobs, or purchase goods.
Configure YJ64_AGENT_API_TOKEN in the deployment environment.
"""
from __future__ import annotations

import hmac
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Make the src-layout package importable in a Vercel Python function deployment.
PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.economics.agent import AgentSourcingRequest, plan_agent_request  # noqa: E402

MAX_BODY_BYTES = 64 * 1024
EXPECTED_PATH = "/api/discovery"


def _json_value(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path != EXPECTED_PATH:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self._send_json(200, {
            "ok": True,
            "service": "yj64-agent-sourcing-planner",
            "schema": "yj64.agent-sourcing-request.v1",
            "mode": "authenticated_planning_only",
            "live_supplier_search": False,
            "purchasing_enabled": False,
        })

    def do_POST(self) -> None:
        if urlparse(self.path).path != EXPECTED_PATH:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        secret = os.environ.get("YJ64_AGENT_API_TOKEN", "")
        if not secret:
            self._send_json(503, {"ok": False, "error": "agent_api_not_configured"})
            return
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + secret):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except (TypeError, ValueError):
            self._send_json(411, {"ok": False, "error": "content_length_required"})
            return
        if length < 1 or length > MAX_BODY_BYTES:
            self._send_json(413, {"ok": False, "error": "invalid_body_size"})
            return
        raw = self.rfile.read(length)
        if len(raw) != length:
            self._send_json(400, {"ok": False, "error": "incomplete_body"})
            return
        try:
            payload = json.loads(raw)
            request = AgentSourcingRequest.from_dict(payload)
            plan = plan_agent_request(request)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return
        except (KeyError, TypeError, ValueError) as exc:
            self._send_json(422, {"ok": False, "error": "invalid_agent_request", "detail": str(exc)})
            return
        self._send_json(200, {
            "ok": True,
            "status": "planned",
            "execution_mode": "planning_only",
            "request": {
                "request_id": request.request_id,
                "agent_id": request.agent_id,
                "task_description": request.task_description,
                "destination_location_id": request.destination.location_id,
            },
            "plan": _json_value(plan),
            "limitations": [
                "No live supplier search has been executed.",
                "No current prices, stock or shipping quotes are asserted.",
                "Technical requirements are carried into the plan; provider-specific technical matching is a later adapter responsibility.",
                "No purchase or order action is available.",
            ],
        })

    def log_message(self, format: str, *args: object) -> None:
        return
