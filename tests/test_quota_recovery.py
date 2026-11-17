import unittest

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


class Cursor:
    def __init__(self, due_ids=None):
        self.due_ids = due_ids or []
        self.statements = []
        self._fetch = None
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        self._fetch = None

    def fetchall(self):
        return [(task_id,) for task_id in self.due_ids]


class Connection:
    def __init__(self, cursor):
        self.value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.value


class QuotaRecoveryTests(unittest.TestCase):
    def store(self, cursor):
        return PostgresCycleStore("postgresql://test", lambda _: Connection(cursor))

    def test_requeues_only_due_quota_tasks(self):
        cursor = Cursor([4, 9])
        result = self.store(cursor).recover_due_quota_tasks(limit=25)
        self.assertEqual(result, [4, 9])
        self.assertEqual(len(cursor.statements), 2)
        failure_update, requeue = (query for query, _ in cursor.statements)
        self.assertIn("blocked_reason = 'quota_exhausted'", failure_update)
        self.assertIn("quota_reset_at <= now()", failure_update)
        self.assertIn("attempts >= max_attempts", failure_update)
        self.assertIn("blocked_reason = 'quota_exhausted'", requeue)
        self.assertIn("quota_reset_at IS NOT NULL", requeue)
        self.assertIn("quota_reset_at <= now()", requeue)
        self.assertIn("attempts < max_attempts", requeue)
        self.assertIn("FOR UPDATE SKIP LOCKED", requeue)
        self.assertIn("blocked_reason = NULL", requeue)
        self.assertIn("quota_reset_at = NULL", requeue)
        self.assertEqual(cursor.statements[1][1], (25,))

    def test_limit_is_bounded(self):
        for invalid in (0, 1001, True, 1.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.store(Cursor()).recover_due_quota_tasks(invalid)

    def test_no_due_tasks_returns_empty(self):
        self.assertEqual(self.store(Cursor()).recover_due_quota_tasks(), [])


if __name__ == "__main__":
    unittest.main()
