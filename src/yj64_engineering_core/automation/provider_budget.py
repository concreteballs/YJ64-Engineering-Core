"""Provider RPM/TPM/concurrency admission planning with rolling windows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class ProviderLimitProfile:
    provider: str
    model: str
    endpoint: str
    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None
    max_concurrency: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_payload_bytes: int | None = None
    tokens_per_minute_includes_output: bool = True
    input_cost_per_million_usd: float | None = None
    output_cost_per_million_usd: float | None = None

    def __post_init__(self):
        if not self.provider.strip() or not self.model.strip() or not self.endpoint.strip():
            raise ValueError("provider, model and endpoint are required")
        for name in (
            "requests_per_minute", "tokens_per_minute", "max_concurrency",
            "max_input_tokens", "max_output_tokens", "max_payload_bytes",
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                raise ValueError(f"{name} must be a positive integer or None")
        if not isinstance(self.tokens_per_minute_includes_output, bool):
            raise ValueError("tokens_per_minute_includes_output must be boolean")
        for name in ("input_cost_per_million_usd", "output_cost_per_million_usd"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
                or value < 0 or value == float("inf") or value != value
            ):
                raise ValueError(f"{name} must be a finite non-negative number or None")


@dataclass(frozen=True)
class CapacityDecision:
    allowed: bool
    action: str
    retry_at: datetime | None
    reason: str
    requests_in_window: int
    tokens_in_window: int
    active_requests: int


def plan_provider_capacity(
    profile: ProviderLimitProfile,
    *,
    input_tokens: int,
    output_tokens: int = 0,
    payload_bytes: int = 0,
    reservations: Iterable[dict] = (),
    now: datetime | None = None,
    reservation_ttl_seconds: int = 300,
) -> CapacityDecision:
    """Check request size, rolling RPM/TPM windows and concurrent reservations.

    Reservations should include recent sent/completed requests as well as active
    reserved/sending/accepted requests. A denied request is scheduled, never slept.
    """
    if not isinstance(profile, ProviderLimitProfile):
        raise ValueError("profile must be a ProviderLimitProfile")
    for name, value in (
        ("input_tokens", input_tokens), ("output_tokens", output_tokens),
        ("payload_bytes", payload_bytes),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if not isinstance(reservation_ttl_seconds, int) or isinstance(reservation_ttl_seconds, bool) or reservation_ttl_seconds < 1:
        raise ValueError("reservation_ttl_seconds must be a positive integer")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if profile.max_payload_bytes is not None and payload_bytes > profile.max_payload_bytes:
        return CapacityDecision(False, "split_or_decompose", None,
                                 "Request body exceeds the provider payload-byte limit", 0, 0, 0)
    if profile.max_input_tokens is not None and input_tokens > profile.max_input_tokens:
        return CapacityDecision(False, "split_or_decompose", None,
                                 "Request exceeds the provider input-token limit", 0, 0, 0)
    if profile.max_output_tokens is not None and output_tokens > profile.max_output_tokens:
        return CapacityDecision(False, "reduce_output_limit", None,
                                 "Requested output exceeds the provider output-token limit", 0, 0, 0)

    request_tokens = input_tokens + (
        output_tokens if profile.tokens_per_minute_includes_output else 0
    )
    if profile.tokens_per_minute is not None and request_tokens > profile.tokens_per_minute:
        return CapacityDecision(False, "split_or_decompose", None,
                                 "One request exceeds the provider TPM budget; split into separately scheduled requests",
                                 0, 0, 0)

    window_start = now - timedelta(seconds=60)
    recent: list[tuple[datetime, int, str, datetime]] = []
    active_all: list[tuple[datetime, int, str, datetime]] = []
    for item in reservations:
        if not isinstance(item, dict):
            raise ValueError("reservations must contain objects")
        created_at = item.get("created_at")
        if not isinstance(created_at, datetime) or created_at.tzinfo is None:
            raise ValueError("reservation created_at must be timezone-aware")
        state = str(item.get("state", "reserved"))
        if state not in {"reserved", "sending", "accepted", "completed", "failed", "unknown"}:
            continue
        tokens = item.get("estimated_tokens", 0)
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
            raise ValueError("reservation estimated_tokens must be non-negative")
        expires_at = item.get("expires_at")
        if expires_at is not None and (
            not isinstance(expires_at, datetime) or expires_at.tzinfo is None
        ):
            raise ValueError("reservation expires_at must be timezone-aware")
        if expires_at is None and state in {"sending", "accepted", "unknown"}:
            effective_expiry = datetime.max.replace(tzinfo=timezone.utc)
        else:
            effective_expiry = expires_at or created_at + timedelta(seconds=reservation_ttl_seconds)
        reservation = (created_at, tokens, state, effective_expiry)
        sent_at = item.get("sent_at")
        if sent_at is not None and (
            not isinstance(sent_at, datetime) or sent_at.tzinfo is None
        ):
            raise ValueError("reservation sent_at must be timezone-aware")
        # An unsent reservation consumes concurrency, but not RPM/TPM.
        # Once the request may have left the process, sent_at is authoritative.
        rolling_at = sent_at
        if rolling_at is None and state in {"completed", "failed"}:
            rolling_at = created_at  # compatibility with historical test inputs
        if rolling_at is not None and rolling_at >= window_start:
            recent.append((rolling_at, tokens, state, reservation[3]))
        if state in {"reserved", "sending", "accepted", "unknown"} and reservation[3] > now:
            active_all.append(reservation)

    requests_used = len(recent)
    tokens_used = sum(item[1] for item in recent)
    active = active_all
    retry_times: list[datetime] = []
    reasons: list[str] = []

    if profile.requests_per_minute is not None and requests_used >= profile.requests_per_minute:
        candidates = [item[0] + timedelta(seconds=60) for item in recent]
        retry_times.append(min(candidates))
        reasons.append("requests-per-minute budget is full")

    if profile.tokens_per_minute is not None and tokens_used + request_tokens > profile.tokens_per_minute:
        candidates = sorted({item[0] + timedelta(seconds=60) for item in recent})
        token_retry = None
        for candidate in candidates:
            remaining = sum(
                item[1] for item in recent
                if item[0] + timedelta(seconds=60) > candidate
            )
            if remaining + request_tokens <= profile.tokens_per_minute:
                token_retry = candidate
                break
        if token_retry is None and candidates:
            token_retry = candidates[-1]
        if token_retry is not None:
            retry_times.append(token_retry)
            reasons.append("tokens-per-minute budget is full")

    if profile.max_concurrency is not None and len(active) >= profile.max_concurrency:
        if any(item[2] == "unknown" for item in active):
            return CapacityDecision(
                False, "hold_for_review", None,
                "An earlier provider request has an unknown outcome and occupies concurrency until reconciled",
                requests_used, tokens_used, len(active),
            )
        known_expiries = [item[3] for item in active if item[2] == "reserved"]
        if known_expiries:
            retry_times.append(min(known_expiries))
        else:
            # Sent requests remain active until explicitly settled. Recheck
            # through the scheduler; never expire them by wall-clock timeout.
            retry_times.append(now + timedelta(seconds=5))
        reasons.append("provider concurrency limit is full")

    if retry_times:
        retry_at = max(retry_times)
        return CapacityDecision(
            False, "schedule_retry", retry_at,
            "; ".join(reasons), requests_used, tokens_used, len(active),
        )
    return CapacityDecision(
        True, "send", None, "provider capacity is available",
        requests_used, tokens_used, len(active),
    )
