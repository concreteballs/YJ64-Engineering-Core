-- Keep the CI event and task queue tables private to trusted server-side code.
ALTER TABLE yj64_ci_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE yj64_task_queue ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE yj64_ci_events FROM anon, authenticated;
REVOKE ALL ON TABLE yj64_task_queue FROM anon, authenticated;

GRANT ALL ON TABLE yj64_ci_events TO service_role;
GRANT ALL ON TABLE yj64_task_queue TO service_role;
GRANT USAGE, SELECT ON SEQUENCE yj64_ci_events_event_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE yj64_task_queue_task_id_seq TO service_role;
