-- 0005: phase 1 of the production-line fix (2026-11-24). Additive only.

-- Set only when the owner presses Start/Resume on a channel. The planner's "3 failed videos in 24h" breaker counts
-- failures after this time, so ordinary row updates (limit pauses, weekly review, settings saves) never forgive them.
alter table public.channels add column if not exists failures_forgiven_at timestamptz;

-- How many videos made from this idea have failed. A failed video gives its idea back to the bank; after 2 failures
-- the idea is retired so a bad topic can't keep failing.
alter table public.ideas add column if not exists fail_count int not null default 0;
