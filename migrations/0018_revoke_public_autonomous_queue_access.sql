-- Keep the autonomous CI ingress and task queue server-only.
-- RLS remains enabled; this also removes table-level access for client roles.
REVOKE ALL ON TABLE public.yj64_ci_events, public.yj64_task_queue
FROM anon, authenticated, PUBLIC;
GRANT ALL ON TABLE public.yj64_ci_events, public.yj64_task_queue
TO service_role;

REVOKE ALL ON SEQUENCE public.yj64_ci_events_event_id_seq, public.yj64_task_queue_task_id_seq
FROM anon, authenticated, PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE public.yj64_ci_events_event_id_seq, public.yj64_task_queue_task_id_seq
TO service_role;
