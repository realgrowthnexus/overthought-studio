-- Worker hardening (from code audit)

-- 1) periodic jobs: once-per-period key, unique across ALL statuses
alter table public.jobs add column if not exists once_key text;
create unique index if not exists jobs_once on public.jobs(once_key) where once_key is not null;

-- 15) cap how many times a job may be parked waiting on a service
alter table public.jobs add column if not exists waits int not null default 0;
alter table public.jobs add column if not exists parked_status text;   -- service status that parked it
alter table public.jobs add column if not exists prev_video_status text;

-- 10) claim_job: recover only jobs whose lane heartbeat (locked_at) is stale; respect max_attempts
create or replace function public.claim_job(p_worker text, p_types text[] default null)
returns setof public.jobs language plpgsql security definer set search_path = public as $$
declare j public.jobs;
begin
  update public.jobs set status = case when attempts >= max_attempts then 'failed' else 'queued' end,
         last_error = coalesce(last_error, '') || ' [recovered: worker stopped responding]',
         locked_by = null, locked_at = null,
         finished_at = case when attempts >= max_attempts then now() else null end
   where status = 'running' and locked_at < now() - interval '10 minutes';

  select * into j from public.jobs
   where status = 'queued' and run_after <= now()
     and (p_types is null or type = any(p_types))
   order by priority asc, run_after asc, id asc
   for update skip locked limit 1;
  if not found then return; end if;
  update public.jobs set status = 'running', locked_by = p_worker, locked_at = now(),
         started_at = now(), attempts = attempts + 1
   where id = j.id returning * into j;
  return next j;
end $$;
revoke all on function public.claim_job(text, text[]) from public, anon, authenticated;

-- 5) server-side sums (PostgREST caps selects at 1000 rows)
create or replace function public.spend_total(p_since timestamptz, p_service text default null)
returns numeric language sql stable security definer set search_path = public as $$
  select coalesce(sum(amount_usd), 0) from public.spend
   where created_at >= p_since and (p_service is null or service = p_service)
$$;
revoke all on function public.spend_total(timestamptz, text) from public, anon;
grant execute on function public.spend_total(timestamptz, text) to authenticated;

-- 24) one active video per idea
create unique index if not exists videos_one_active_per_idea on public.videos(idea_id)
  where idea_id is not null and status not in ('failed','rejected');

-- 21) column-level revoke does not beat table grants: re-grant only safe columns
revoke select, update on public.tiktok_accounts from authenticated, anon;
grant select (id, open_id, username, display_name, avatar_url, access_expires_at, refresh_expires_at, scopes, status,
              status_message, follower_count, following_count, likes_count, video_count, is_verified, creator_info,
              last_synced_at, created_at, updated_at) on public.tiktok_accounts to authenticated;
grant update (status, status_message) on public.tiktok_accounts to authenticated;
