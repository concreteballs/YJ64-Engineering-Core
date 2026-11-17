"""Provider error classification and bounded retry planning.

This module is deliberately provider-agnostic and has no network dependencies.
It never decides to retry permanent billing/authentication failures.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Mapping


@dataclass(frozen=True)
class RetryDecision:
    classification: str
    action: str
    retryable: bool
    delay_seconds: int | None
    reason: str


def _headers_map(headers: Mapping[str, object] | None) -> dict[str, str]:
    return {str(k).lower(): str(v).strip() for k, v in (headers or {}).items()}


def _retry_after(headers: dict[str, str], now: datetime) -> int | None:
    raw = headers.get("retry-after")
    if raw:
        try:
            return max(0, min(86400, int(float(raw))))
        except ValueError:
            try:
                when = parsedate_to_datetime(raw)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                return max(0, min(86400, int((when - now).total_seconds())))
            except (TypeError, ValueError, OverflowError):
                pass
    for key in ("x-ratelimit-reset", "ratelimit-reset", "x-quota-reset"):
        raw = headers.get(key)
        if raw:
            try:
                value = float(raw)
                # Epoch seconds are common; relative seconds are also accepted.
                seconds = value - now.timestamp() if value > 1_000_000_000 else value
                return max(0, min(86400, int(seconds)))
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def classify_provider_error(
    status_code: int | None,
    error: str = "",
    headers: Mapping[str, object] | None = None,
    *,
    attempt: int = 1,
    now: datetime | None = None,
    jitter_fraction: float = 0.0,
    base_delay_seconds: int = 5,
    max_delay_seconds: int = 900,
) -> RetryDecision:
    """Classify a provider failure and return a bounded, durable scheduling hint.

    jitter_fraction is injected by the caller (normally random.uniform(0, 0.2))
    so tests and persisted retry decisions remain deterministic.
    """
    if attempt < 1:
        raise ValueError("attempt must be positive")
    if not 0 <= jitter_fraction <= 0.5:
        raise ValueError("jitter_fraction must be between 0 and 0.5")
    if base_delay_seconds < 1 or max_delay_seconds < base_delay_seconds:
        raise ValueError("invalid backoff bounds")

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    hdr = _headers_map(headers)
    message = str(error or "").lower()
    retry_hint = _retry_after(hdr, now)

    quota_markers = (
        "daily quota", "monthly quota", "daily limit", "monthly limit",
        "requests per day", "tokens per day", "requests per month", "tokens per month",
        "billing limit", "quota exceeded", "exceeded your quota", "current quota",
        "usage limit", "insufficient_quota", "hard limit",
    )
    if any(marker in message for marker in quota_markers):
        reset = retry_hint
        return RetryDecision("quota_exhausted", "block_until_reset", False, reset,
                             "Provider quota or billing limit is exhausted")

    if status_code == 413 or any(x in message for x in
                                 ("payload too large", "request too large", "input too large")):
        return RetryDecision("payload_too_large", "split_or_decompose", False, None,
                             "Do not resend the same oversized payload")

    if any(x in message for x in ("context length", "context window", "maximum context",
                                  "too many tokens", "token limit exceeded")):
        return RetryDecision("context_overflow", "rebuild_smaller_context", False, None,
                             "Rebuild a smaller complete context; do not truncate or resend unchanged")

    if status_code == 429:
        delay = retry_hint if retry_hint is not None else min(
            max_delay_seconds, base_delay_seconds * (2 ** min(attempt - 1, 20))
        )
        if retry_hint is None:
            delay = min(max_delay_seconds, int(delay * (1 + jitter_fraction)))
        return RetryDecision("rate_limited", "schedule_retry", True, delay,
                             "Persist retry time and release the worker lease")

    if status_code == 408 or status_code is not None and 500 <= status_code <= 599:
        delay = retry_hint if retry_hint is not None else min(
            max_delay_seconds, base_delay_seconds * (2 ** min(attempt - 1, 20))
        )
        if retry_hint is None:
            delay = min(max_delay_seconds, int(delay * (1 + jitter_fraction)))
        return RetryDecision("transient_provider_error", "schedule_retry", True, delay,
                             "Transient provider failure")

    if any(x in message for x in ("concurrency limit", "too many concurrent", "parallel request limit")):
        delay = retry_hint if retry_hint is not None else min(
            max_delay_seconds, base_delay_seconds * (2 ** min(attempt - 1, 20))
        )
        return RetryDecision("concurrency_limited", "schedule_retry", True, delay,
                             "Reduce concurrency and retry after the indicated delay")

    if status_code in (400, 401, 403, 404, 422):
        return RetryDecision("permanent_provider_error", "fail_or_require_configuration", False, None,
                             "Do not retry invalid request, authentication, permission, or model configuration")

    return RetryDecision("unknown_provider_error", "hold_for_review", False, None,
                         "Unknown provider failure requires classification before retry")
