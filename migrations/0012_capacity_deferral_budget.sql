-- Capacity waits are scheduling deferrals, not failed model attempts.
ALTER TABLE yj64_task_queue
    ADD COLUMN IF NOT EXISTS capacity_deferrals INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_capacity_deferrals INTEGER NOT NULL DEFAULT 1000;
ALTER TABLE yj64_task_queue
    ADD CONSTRAINT yj64_task_queue_capacity_deferrals_nonnegative
    CHECK (
        capacity_deferrals >= 0
        AND max_capacity_deferrals > 0
        AND capacity_deferrals <= max_capacity_deferrals
    );
