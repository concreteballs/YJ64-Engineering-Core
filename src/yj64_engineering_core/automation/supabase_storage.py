"""Private Supabase Storage backend for immutable model-result artifacts.

This server-side adapter requires a private bucket and a server-only secret key.
It never returns signed/public URLs; callers receive opaque artifact references.
"""
from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable


_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SupabaseStorageArtifactStore:
    """Immutable artifact storage backed by a private Supabase Storage bucket.

    The service key is held only in memory and sent only in server-side HTTPS
    requests. It must never be placed in browser/client code or logged.
    """

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        bucket: str = "yj64-private-artifacts",
        timeout_seconds: float = 20.0,
        max_upload_bytes: int = 6 * 1024 * 1024,
        opener: Callable | None = None,
    ) -> None:
        if not isinstance(supabase_url, str) or not supabase_url.strip():
            raise ValueError("supabase_url is required")
        parsed = urllib.parse.urlsplit(supabase_url.strip().rstrip("/"))
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("supabase_url must be an HTTPS origin")
        if parsed.path or parsed.query or parsed.fragment:
            raise ValueError("supabase_url must not contain a path, query or fragment")
        if not isinstance(service_role_key, str) or not service_role_key.strip():
            raise ValueError("service_role_key is required")
        if not isinstance(bucket, str) or not _BUCKET_RE.fullmatch(bucket):
            raise ValueError("bucket must be a valid Storage bucket identifier")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")
        if (
            not isinstance(max_upload_bytes, int)
            or isinstance(max_upload_bytes, bool)
            or max_upload_bytes < 1
        ):
            raise ValueError("max_upload_bytes must be positive")
        self._base_url = f"{parsed.scheme}://{parsed.netloc}"
        self._key = service_role_key.strip()
        self.bucket = bucket
        self.timeout_seconds = float(timeout_seconds)
        self.max_upload_bytes = max_upload_bytes
        self._opener = opener or urllib.request.urlopen

    @classmethod
    def from_environment(cls, **kwargs) -> "SupabaseStorageArtifactStore":
        """Build from server-only environment variables; never expose these client-side."""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured server-side"
            )
        return cls(supabase_url=url, service_role_key=key, **kwargs)

    def put(self, *, namespace: str, content: bytes, content_type: str) -> str:
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("namespace is required")
        segments = namespace.strip("/").split("/")
        if any(not _SEGMENT_RE.fullmatch(part) or part in {".", ".."} for part in segments):
            raise ValueError("namespace contains an invalid path segment")
        if not isinstance(content, bytes) or not content:
            raise ValueError("content must be non-empty bytes")
        if len(content) > self.max_upload_bytes:
            raise ValueError("artifact exceeds configured standard-upload size; use resumable upload")
        if not isinstance(content_type, str) or not content_type.strip():
            raise ValueError("content_type is required")

        digest = hashlib.sha256(content).hexdigest()
        object_path = "/".join((*segments, digest))
        url = self._object_url(object_path)
        request = urllib.request.Request(
            url,
            data=content,
            headers={
                **self._auth_headers(),
                "Content-Type": content_type.strip(),
                "Cache-Control": "no-store",
                "x-upsert": "false",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    raise RuntimeError(f"Supabase Storage upload returned HTTP {status}")
        except urllib.error.HTTPError as exc:
            body = exc.read(2048).decode("utf-8", errors="replace").lower()
            duplicate = exc.code in {400, 409} and (
                "already exists" in body or "duplicate" in body
            )
            if not duplicate:
                raise RuntimeError(
                    f"Supabase Storage upload failed with HTTP {exc.code}"
                ) from None
            # Content-addressed path: an existing object is acceptable only if
            # its bytes exactly match the requested artifact.
            existing = self.get(f"supabase-storage://{self.bucket}/{object_path}")
            if existing != content:
                raise RuntimeError("existing artifact content does not match its SHA-256 path")
        return f"supabase-storage://{self.bucket}/{object_path}"

    def get(self, artifact_ref: str) -> bytes:
        if not isinstance(artifact_ref, str) or not artifact_ref:
            raise ValueError("artifact_ref is required")
        parsed = urllib.parse.urlsplit(artifact_ref)
        if (
            parsed.scheme != "supabase-storage"
            or parsed.netloc != self.bucket
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("artifact_ref is not an opaque reference for the configured bucket")
        object_path = parsed.path.lstrip("/")
        segments = object_path.split("/")
        if (
            len(segments) < 2
            or any(not _SEGMENT_RE.fullmatch(part) or part in {".", ".."} for part in segments[:-1])
            or not _SHA256_RE.fullmatch(segments[-1])
        ):
            raise ValueError("artifact_ref has an invalid content-addressed object path")

        request = urllib.request.Request(
            self._object_url(object_path, authenticated=True),
            headers=self._auth_headers(),
            method="GET",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RuntimeError(f"Supabase Storage download returned HTTP {status}")
                content = response.read(self.max_upload_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Supabase Storage download failed with HTTP {exc.code}"
            ) from None
        if len(content) > self.max_upload_bytes:
            raise RuntimeError("downloaded artifact exceeds configured size limit")
        if hashlib.sha256(content).hexdigest() != segments[-1]:
            raise RuntimeError("downloaded artifact failed SHA-256 integrity verification")
        return content

    def _object_url(self, object_path: str, *, authenticated: bool = False) -> str:
        encoded_bucket = urllib.parse.quote(self.bucket, safe="")
        encoded_path = urllib.parse.quote(object_path, safe="/")
        route = "authenticated" if authenticated else ""
        middle = f"/{route}" if route else ""
        return (
            f"{self._base_url}/storage/v1/object{middle}/"
            f"{encoded_bucket}/{encoded_path}"
        )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
        }
