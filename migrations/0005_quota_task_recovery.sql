-- Track why a task is blocked so quota recovery never unblocks unrelated work.
ALTER TABLE yj64_task_queue
    ADD COLUMN IF NOT EXISTS blocked_reason TEXT,
    ADD COLUMN IF NOT EXISTS quota_reset_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS yj64_task_queue_quota_recovery_idx
    ON yj64_task_queue (quota_reset_at, task_id)
    WHERE state = 'blocked' AND blocked_reason = 'quota_exhausted';
