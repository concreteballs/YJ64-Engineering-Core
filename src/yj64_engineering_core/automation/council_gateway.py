"""Authenticated client for the YJ-64 application's native council API.

This is a transport adapter only. It never routes individual models, creates
consensus rounds, or treats a council response as verified engineering evidence.
The default HTTP paths are the proposed yj64.council-api.v1 contract and must be
implemented by the YJ-64 application before live end-to-end use.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping


PROTOCOL_VERSION = "yj64.council-api.v1"
EXECUTION_STATUSES = {
    "accepted", "running", "completed", "blocked", "failed", "cancelled",
}
TERMINAL_STATUSES = {"completed", "blocked", "failed", "cancelled"}
SUBSTANTIVE_OUTCOMES = {
    "consensus", "qualified_consensus",
    "unresolved_disagreement", "insufficient_evidence",
}
MODES = {"consensus", "critique"}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SENSITIVE_CONTEXT_KEY = re.compile(r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|authorization|private[_-]?messages|system[_-]?prompt|hidden[_-]?rating)", re.I)
_PRIVATE_RESULT_KEY = re.compile(r"(?:private[_-]?rating|competence[_-]?score|individual[_-]?vote|individual[_-]?ballot|hidden[_-]?vote|private[_-]?message|system[_-]?prompt|api[_-]?key|access[_-]?token)", re.I)


class CouncilGatewayError(RuntimeError):
    """Safe, classified API error; response bodies and credentials are not exposed."""

    def __init__(
        self,
        classification: str,
        *,
        retryable: bool = False,
        http_status: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(classification)
        self.classification = classification
        self.retryable = retryable
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class CouncilRequest:
    """A bounded request for the YJ-64-owned consensus or critique protocol."""

    mode: str
    title: str
    prompt: str
    correlation_id: str
    idempotency_key: str
    context: Mapping[str, Any] | None = None
    evidence_refs: tuple[str, ...] = ()
    max_rounds: int = 3
    timeout_seconds: int = 1800
    max_output_tokens: int = 12000
    voting_enabled: bool = False
    weighted_voting_enabled: bool = False
    allow_early_stop: bool = True

    def to_payload(self, agent_id: str) -> dict[str, Any]:
        if self.mode not in MODES:
            raise ValueError("mode must be consensus or critique")
        if not isinstance(self.voting_enabled, bool) or not isinstance(self.weighted_voting_enabled, bool):
            raise ValueError("voting flags must be booleans")
        if not isinstance(self.allow_early_stop, bool):
            raise ValueError("allow_early_stop must be a boolean")
        if self.weighted_voting_enabled and not self.voting_enabled:
            raise ValueError("weighted voting requires voting_enabled")
        for name, value, maximum in (
            ("title", self.title, 500),
            ("prompt", self.prompt, 50000),
            ("correlation_id", self.correlation_id, 128),
            ("idempotency_key", self.idempotency_key, 256),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"{name} must be non-empty and within its size limit")
        if not _ID_RE.fullmatch(self.correlation_id):
            raise ValueError("correlation_id contains unsupported characters")
        if not isinstance(self.idempotency_key, str) or not 8 <= len(self.idempotency_key) <= 256:
            raise ValueError("idempotency_key must contain 8-256 characters")
        if not isinstance(agent_id, str) or not _ID_RE.fullmatch(agent_id):
            raise ValueError("agent_id is invalid")
        if self.context is not None and not isinstance(self.context, Mapping):
            raise ValueError("context must be an object")
        if not isinstance(self.evidence_refs, (tuple, list)) or len(self.evidence_refs) > 100:
            raise ValueError("evidence_refs must contain at most 100 references")
        if any(not isinstance(ref, str) or not ref.strip() or len(ref) > 2048 for ref in self.evidence_refs):
            raise ValueError("each evidence reference must be non-empty and bounded")
        for name, value, minimum, maximum in (
            ("max_rounds", self.max_rounds, 1, 10),
            ("timeout_seconds", self.timeout_seconds, 30, 86400),
            ("max_output_tokens", self.max_output_tokens, 256, 100000),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}")
        _validate_context(dict(self.context or {}))
        if len(_canonical_json(dict(self.context or {}))) > 256 * 1024:
            raise ValueError("context exceeds the 256 KiB request limit")
        return {
            "protocol_version": PROTOCOL_VERSION,
            "agent_id": agent_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "mode": self.mode,
            "task": {
                "title": self.title.strip(),
                "prompt": self.prompt,
                "context": dict(self.context or {}),
                "evidence_refs": list(self.evidence_refs),
            },
            "limits": {
                "max_rounds": self.max_rounds,
                "timeout_seconds": self.timeout_seconds,
                "max_output_tokens": self.max_output_tokens,
                "minimum_critique_rounds": 1,
                "allow_early_stop": self.allow_early_stop,
            },
            "voting": {
                "enabled": self.voting_enabled,
                "weighted": self.weighted_voting_enabled,
            },
        }


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must contain finite JSON-compatible values") from exc


def _validate_context(value: Any, *, depth: int = 0) -> None:
    """Reject credential/private-state fields before context leaves the agent."""
    if depth > 8:
        raise ValueError("context nesting exceeds the supported depth")
    if isinstance(value, Mapping):
        if len(value) > 200:
            raise ValueError("context object has too many fields")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("context keys must be non-empty strings")
            if _SENSITIVE_CONTEXT_KEY.search(key):
                raise ValueError("context contains a credential or private-state field")
            _validate_context(item, depth=depth + 1)
    elif isinstance(value, (list, tuple)):
        if len(value) > 500:
            raise ValueError("context list exceeds the supported size")
        for item in value:
            _validate_context(item, depth=depth + 1)
    elif isinstance(value, str):
        if len(value) > 50000:
            raise ValueError("context string exceeds the supported size")
    elif value is None or isinstance(value, (bool, int, float)):
        _canonical_json(value)
    else:
        raise ValueError("context must contain JSON-compatible values")


def _reject_private_result_fields(value: Any, *, depth: int = 0) -> None:
    if depth > 12:
        raise CouncilGatewayError("result_nesting_too_deep")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and _PRIVATE_RESULT_KEY.search(key):
                raise CouncilGatewayError("council_result_contains_private_fields")
            _reject_private_result_fields(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _reject_private_result_fields(item, depth=depth + 1)


def _safe_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"{name} is missing or invalid")
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a machine credential to a redirect target.
        return None


class CouncilGatewayClient:
    """HTTPS client for the versioned external-agent council API."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        agent_id: str = "yj64-engineering-core",
        timeout_seconds: float = 20.0,
        max_response_bytes: int = 2 * 1024 * 1024,
        opener: Callable | None = None,
        allow_insecure_http: bool = False,
        submit_path: str = "/api/v1/external-agents/council/requests",
        status_path_template: str = "/api/v1/external-agents/council/requests/{request_id}",
        result_path_template: str = "/api/v1/external-agents/council/requests/{request_id}/result",
        cancel_path_template: str = "/api/v1/external-agents/council/requests/{request_id}/cancel",
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url is required")
        parsed = urllib.parse.urlsplit(base_url.strip().rstrip("/"))
        allowed_schemes = {"https"} | ({"http"} if allow_insecure_http else set())
        if parsed.scheme not in allowed_schemes or not parsed.netloc:
            raise ValueError("base_url must be an HTTPS origin")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url must not contain credentials, query or fragment")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token is required")
        _safe_id(agent_id, "agent_id")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool) or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or not 1024 <= max_response_bytes <= 10 * 1024 * 1024
        ):
            raise ValueError("max_response_bytes must be between 1 KiB and 10 MiB")
        self._origin = f"{parsed.scheme}://{parsed.netloc}"
        self._base_path = parsed.path.rstrip("/")
        self._token = token.strip()
        self.agent_id = agent_id
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = max_response_bytes
        self.submit_path = self._validate_route(submit_path, "submit_path")
        self.status_path_template = self._validate_route(status_path_template, "status_path_template", request_id=True)
        self.result_path_template = self._validate_route(result_path_template, "result_path_template", request_id=True)
        self.cancel_path_template = self._validate_route(cancel_path_template, "cancel_path_template", request_id=True)
        self._opener = opener or urllib.request.build_opener(_NoRedirect()).open

    @classmethod
    def from_environment(cls, **kwargs) -> "CouncilGatewayClient":
        """Read machine credentials only from the worker's server environment."""
        base_url = os.environ.get("YJ64_COUNCIL_API_URL", "")
        token = os.environ.get("YJ64_COUNCIL_AGENT_TOKEN", "")
        agent_id = os.environ.get("YJ64_COUNCIL_AGENT_ID", "yj64-engineering-core")
        if not base_url or not token:
            raise RuntimeError(
                "YJ64_COUNCIL_API_URL and YJ64_COUNCIL_AGENT_TOKEN are required"
            )
        return cls(
            base_url=base_url,
            token=token,
            agent_id=agent_id,
            submit_path=os.environ.get("YJ64_COUNCIL_SUBMIT_PATH", "/api/v1/external-agents/council/requests"),
            status_path_template=os.environ.get("YJ64_COUNCIL_STATUS_PATH", "/api/v1/external-agents/council/requests/{request_id}"),
            result_path_template=os.environ.get("YJ64_COUNCIL_RESULT_PATH", "/api/v1/external-agents/council/requests/{request_id}/result"),
            cancel_path_template=os.environ.get("YJ64_COUNCIL_CANCEL_PATH", "/api/v1/external-agents/council/requests/{request_id}/cancel"),
            **kwargs,
        )

    def submit(self, request: CouncilRequest) -> dict[str, Any]:
        if not isinstance(request, CouncilRequest):
            raise TypeError("request must be a CouncilRequest")
        payload = request.to_payload(self.agent_id)
        data = self._request(
            "POST", self.submit_path,
            payload=payload,
            extra_headers={"Idempotency-Key": request.idempotency_key},
        )
        if data.get("protocol_version") != PROTOCOL_VERSION:
            raise CouncilGatewayError("unsupported_protocol_version")
        request_id = _safe_id(data.get("request_id"), "request_id")
        session_id = _safe_id(data.get("session_id"), "session_id")
        status = data.get("status")
        if status not in {"accepted", "running"}:
            raise CouncilGatewayError("invalid_submit_status")
        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request_id,
            "session_id": session_id,
            "status": status,
            "agent_id": self.agent_id,
            "correlation_id": request.correlation_id,
            "idempotency_key": request.idempotency_key,
        }

    def get_status(self, request_id: str) -> dict[str, Any]:
        request_id = _safe_id(request_id, "request_id")
        data = self._request(
            "GET", self.status_path_template.format(request_id=urllib.parse.quote(request_id, safe=""))
        )
        if data.get("protocol_version") != PROTOCOL_VERSION:
            raise CouncilGatewayError("unsupported_protocol_version")
        returned_id = _safe_id(data.get("request_id"), "request_id")
        session_id = _safe_id(data.get("session_id"), "session_id")
        if returned_id != request_id:
            raise CouncilGatewayError("request_id_mismatch")
        status = data.get("status")
        if status not in EXECUTION_STATUSES:
            raise CouncilGatewayError("invalid_execution_status")
        progress = data.get("progress")
        if progress is not None and not isinstance(progress, dict):
            raise CouncilGatewayError("invalid_progress")
        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": returned_id,
            "session_id": session_id,
            "status": status,
            "progress": progress or {},
            "updated_at": data.get("updated_at"),
        }

    def get_result(self, request_id: str, session_id: str) -> dict[str, Any]:
        request_id = _safe_id(request_id, "request_id")
        session_id = _safe_id(session_id, "session_id")
        data = self._request(
            "GET",
            self.result_path_template.format(request_id=urllib.parse.quote(request_id, safe="")),
        )
        if data.get("protocol_version") != PROTOCOL_VERSION:
            raise CouncilGatewayError("unsupported_protocol_version")
        if data.get("request_id") != request_id or data.get("session_id") != session_id:
            raise CouncilGatewayError("council_result_identity_mismatch")
        if data.get("status") != "completed":
            raise CouncilGatewayError("council_result_not_completed")
        _reject_private_result_fields(data)
        outcome = data.get("outcome")
        if outcome not in SUBSTANTIVE_OUTCOMES:
            raise CouncilGatewayError("invalid_substantive_outcome")
        summary = data.get("summary")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 50000:
            raise CouncilGatewayError("invalid_result_summary")
        collections = (
            "claims", "participant_positions", "dissent", "evidence",
            "unresolved_questions", "assumptions", "limitations",
            "tests_and_simulations",
        )
        for key in collections:
            value = data.get(key, [])
            if not isinstance(value, list):
                raise CouncilGatewayError("invalid_result_structure")
        claims = data.get("claims", [])
        for claim in claims:
            if (
                not isinstance(claim, dict)
                or not isinstance(claim.get("claim_id"), str) or not claim.get("claim_id", "").strip()
                or not isinstance(claim.get("statement"), str) or not claim.get("statement", "").strip()
                or claim.get("epistemic_type") not in {"fact", "inference", "hypothesis", "test_result"}
                or not isinstance(claim.get("reasoning"), str)
                or not isinstance(claim.get("evidence_refs", []), list)
                or any(not isinstance(ref, str) or not ref.strip() for ref in claim.get("evidence_refs", []))
            ):
                raise CouncilGatewayError("invalid_claim_structure")
        evidence = data.get("evidence", [])
        for item in evidence:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("evidence_id"), str) or not item.get("evidence_id", "").strip()
                or not isinstance(item.get("reference"), str) or not item.get("reference", "").strip()
                or not isinstance(item.get("description"), str) or not item.get("description", "").strip()
                or item.get("evidence_type") not in {"source", "artifact", "test", "simulation", "measurement"}
            ):
                raise CouncilGatewayError("invalid_evidence_structure")
        for item in data.get("participant_positions", []):
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("participant_id"), str) or not item.get("participant_id", "").strip()
                or not isinstance(item.get("position"), str) or not item.get("position", "").strip()
                or not isinstance(item.get("rationale"), str)
            ):
                raise CouncilGatewayError("invalid_participant_position")
        for item in data.get("dissent", []):
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("participant_id"), str) or not item.get("participant_id", "").strip()
                or not isinstance(item.get("reason"), str) or not item.get("reason", "").strip()
            ):
                raise CouncilGatewayError("invalid_dissent_structure")
        if any(not isinstance(item, dict) for item in data.get("tests_and_simulations", [])):
            raise CouncilGatewayError("invalid_result_structure")
        if any(not isinstance(item, str) for key in ("unresolved_questions", "assumptions", "limitations") for item in data.get(key, [])):
            raise CouncilGatewayError("invalid_result_structure")
        rounds = data.get("rounds_completed")
        if rounds is not None and (
            not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 0
        ):
            raise CouncilGatewayError("invalid_round_count")
        if data.get("completion_reason") is not None and not isinstance(data.get("completion_reason"), str):
            raise CouncilGatewayError("invalid_completion_reason")
        voting_summary = data.get("voting_summary")
        if voting_summary is not None:
            if not isinstance(voting_summary, dict):
                raise CouncilGatewayError("invalid_voting_summary")
            allowed_voting_fields = {
                "enabled", "weighted_enabled", "majority_result",
                "weighted_result", "aggregate_counts",
            }
            if set(voting_summary) - allowed_voting_fields:
                raise CouncilGatewayError("invalid_voting_summary")
            for flag in ("enabled", "weighted_enabled"):
                if flag in voting_summary and not isinstance(voting_summary[flag], bool):
                    raise CouncilGatewayError("invalid_voting_summary")
            vote_results = {"FOR", "AGAINST", "ABSTAIN", "CONDITIONAL", "NO_MAJORITY"}
            for key in ("majority_result", "weighted_result"):
                if key in voting_summary and voting_summary[key] not in vote_results:
                    raise CouncilGatewayError("invalid_voting_summary")
            counts = voting_summary.get("aggregate_counts", {})
            if not isinstance(counts, dict) or any(
                not isinstance(count, int) or isinstance(count, bool) or count < 0
                for count in counts.values()
            ):
                raise CouncilGatewayError("invalid_voting_summary")
        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request_id,
            "session_id": session_id,
            "status": "completed",
            "outcome": outcome,
            "summary": summary,
            "claims": data.get("claims", []),
            "participant_positions": data.get("participant_positions", []),
            "dissent": data.get("dissent", []),
            "evidence": data.get("evidence", []),
            "unresolved_questions": data.get("unresolved_questions", []),
            "assumptions": data.get("assumptions", []),
            "limitations": data.get("limitations", []),
            "rounds_completed": data.get("rounds_completed"),
            "completion_reason": data.get("completion_reason"),
            "tests_and_simulations": data.get("tests_and_simulations", []),
            "voting_summary": voting_summary,
        }

    def cancel(self, request_id: str) -> dict[str, Any]:
        request_id = _safe_id(request_id, "request_id")
        data = self._request(
            "POST",
            self.cancel_path_template.format(request_id=urllib.parse.quote(request_id, safe="")),
            payload={"protocol_version": PROTOCOL_VERSION, "agent_id": self.agent_id},
        )
        if data.get("protocol_version") != PROTOCOL_VERSION:
            raise CouncilGatewayError("unsupported_protocol_version")
        if data.get("request_id") != request_id or data.get("status") not in TERMINAL_STATUSES:
            raise CouncilGatewayError("invalid_cancel_response")
        return {"request_id": request_id, "status": data["status"]}

    @staticmethod
    def _validate_route(value: str, name: str, *, request_id: bool = False) -> str:
        if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
            raise ValueError(f"{name} must be an absolute path on the configured API origin")
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError(f"{name} must not contain an origin, query or fragment")
        if any(part in {".", ".."} for part in parsed.path.split("/")):
            raise ValueError(f"{name} contains an invalid path segment")
        if request_id:
            if value.count("{request_id}") != 1 or set(re.findall(r"{([^{}]+)}", value)) != {"request_id"}:
                raise ValueError(f"{name} must contain exactly one {{request_id}} placeholder")
        elif "{" in value or "}" in value:
            raise ValueError(f"{name} must not contain path placeholders")
        return value

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        body = _canonical_json(payload) if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "X-YJ64-Protocol-Version": PROTOCOL_VERSION,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if extra_headers:
            headers.update(dict(extra_headers))
        url = self._origin + self._base_path + path
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                if not 200 <= status < 300:
                    raise CouncilGatewayError(
                        "council_api_http_error",
                        retryable=status == 429 or status >= 500,
                        http_status=status,
                    )
                raw = response.read(self.max_response_bytes + 1)
        except CouncilGatewayError:
            raise
        except urllib.error.HTTPError as exc:
            retry_after = None
            try:
                retry_after = int(exc.headers.get("Retry-After", "")) if exc.headers else None
            except (TypeError, ValueError):
                pass
            raise CouncilGatewayError(
                "council_api_http_error",
                retryable=exc.code == 429 or exc.code >= 500,
                http_status=exc.code,
                retry_after_seconds=retry_after,
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise CouncilGatewayError("council_api_transport_error", retryable=True) from None
        if len(raw) > self.max_response_bytes:
            raise CouncilGatewayError("council_api_response_too_large")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CouncilGatewayError("council_api_invalid_json") from None
        if not isinstance(data, dict):
            raise CouncilGatewayError("council_api_invalid_response")
        return data
