import io
import os
import unittest
import urllib.error
from unittest.mock import patch

from yj64_engineering_core.automation.supabase_storage import (
    SupabaseStorageArtifactStore,
)


class FakeResponse:
    def __init__(self, body=b"", status=200):
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self._body if limit < 0 else self._body[:limit]


class FakeStorageHTTP:
    def __init__(self):
        self.objects = {}
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        key = request.full_url.split("/storage/v1/object/")[-1]
        if request.method == "POST":
            if key in self.objects:
                raise urllib.error.HTTPError(
                    request.full_url, 400, "Bad Request", {},
                    io.BytesIO(b'{"message":"The resource already exists"}'),
                )
            self.objects[key] = request.data
            return FakeResponse(b'{"Key":"stored"}')
        if request.method == "GET":
            if key not in self.objects:
                raise urllib.error.HTTPError(
                    request.full_url, 404, "Not Found", {}, io.BytesIO(b"not found")
                )
            return FakeResponse(self.objects[key])
        raise AssertionError(f"Unexpected method: {request.method}")


class SupabaseStorageArtifactStoreTests(unittest.TestCase):
    def make_store(self, http=None, **kwargs):
        return SupabaseStorageArtifactStore(
            supabase_url="https://project-ref.supabase.co",
            service_role_key="server-only-test-secret",
            bucket="yj64-private-artifacts",
            opener=http or FakeStorageHTTP(),
            **kwargs,
        )

    def test_upload_and_download_round_trip_with_private_authenticated_path(self):
        http = FakeStorageHTTP()
        store = self.make_store(http)
        payload = b'{"result":"durable"}'
        ref = store.put(
            namespace="model-results/task-1",
            content=payload,
            content_type="application/json",
        )
        self.assertTrue(ref.startswith(
            "supabase-storage://yj64-private-artifacts/model-results/task-1/"
        ))
        self.assertEqual(store.get(ref), payload)
        self.assertEqual([r[0].method for r in http.requests], ["POST", "GET"])
        self.assertIn("/storage/v1/object/authenticated/", http.requests[1][0].full_url)
        self.assertEqual(http.requests[0][0].headers["X-upsert"], "false")
        self.assertEqual(http.requests[0][0].headers["Apikey"], "server-only-test-secret")
        self.assertEqual(http.requests[0][1], 20.0)

    def test_content_addressing_makes_duplicate_upload_idempotent(self):
        http = FakeStorageHTTP()
        store = self.make_store(http)
        payload = b"same immutable response"
        first = store.put(namespace="responses", content=payload, content_type="text/plain")
        second = store.put(namespace="responses", content=payload, content_type="text/plain")
        self.assertEqual(first, second)
        self.assertEqual(store.get(first), payload)
        self.assertEqual([r[0].method for r in http.requests], ["POST", "POST", "GET"])

    def test_corrupt_download_is_rejected_by_sha256(self):
        http = FakeStorageHTTP()
        store = self.make_store(http)
        ref = store.put(namespace="responses", content=b"valid", content_type="text/plain")
        key = http.requests[0][0].full_url.split("/storage/v1/object/")[-1]
        http.objects[key] = b"corrupt"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            store.get(ref)

    def test_signed_or_foreign_artifact_references_are_rejected(self):
        store = self.make_store()
        with self.assertRaisesRegex(ValueError, "opaque reference"):
            store.get(
                "supabase-storage://yj64-private-artifacts/responses/"
                + "a" * 64 + "?token=secret"
            )
        with self.assertRaisesRegex(ValueError, "configured bucket"):
            store.get("supabase-storage://other-bucket/responses/" + "a" * 64)

    def test_invalid_namespace_and_oversized_upload_are_rejected_before_network(self):
        http = FakeStorageHTTP()
        store = self.make_store(http, max_upload_bytes=4)
        with self.assertRaisesRegex(ValueError, "path segment"):
            store.put(namespace="../escape", content=b"x", content_type="text/plain")
        with self.assertRaisesRegex(ValueError, "exceeds configured"):
            store.put(namespace="responses", content=b"12345", content_type="text/plain")
        self.assertEqual(http.requests, [])

    def test_invalid_url_and_empty_secret_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTPS origin"):
            SupabaseStorageArtifactStore(
                supabase_url="http://project-ref.supabase.co",
                service_role_key="secret",
            )
        with self.assertRaisesRegex(ValueError, "service_role_key"):
            SupabaseStorageArtifactStore(
                supabase_url="https://project-ref.supabase.co",
                service_role_key=" ",
            )

    def test_environment_factory_requires_server_side_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must be configured server-side"):
                SupabaseStorageArtifactStore.from_environment()
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://project-ref.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "server-secret",
        }, clear=True):
            store = SupabaseStorageArtifactStore.from_environment()
            self.assertEqual(store.bucket, "yj64-private-artifacts")


if __name__ == "__main__":
    unittest.main()
