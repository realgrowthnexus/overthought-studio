-- Overthought Studio: core schema
-- All tables have RLS on. Admins (rows in public.admins) get full access through
-- the dashboard; the worker uses the service role, which bypasses RLS.
-- public.secrets has NO client policies: only server code with the service role can touch it.

create extension if not exists pgcrypto;

-- ---------- helpers ----------
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at = now(); return new; end $$;

create table public.admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now()
);

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admins where user_id = auth.uid())
$$;

-- ---------- TikTok accounts ----------
create table public.tiktok_accounts (
  id uuid primary key default gen_random_uuid(),
  open_id text unique not null,
  username text,
  display_name text,
  avatar_url text,
  access_token_enc text,
  refresh_token_enc text,
  access_expires_at timestamptz,
  refresh_expires_at timestamptz,
  scopes text[] not null default '{}',
  status text not null default 'connected' check (status in ('connected','expired','revoked','error')),
  status_message text,
  follower_count int,
  following_count int,
  likes_count bigint,
  video_count int,
  is_verified boolean,
  creator_info jsonb,              -- latest query_creator_info result (privacy options, max duration…)
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_tta_upd before update on public.tiktok_accounts for each row execute function touch_updated_at();

-- ---------- channels ----------
create table public.channels (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null check (slug ~ '^[a-z0-9-]{2,40}$'),
  name text not null,
  niche text not null,
  description text not null default '',
  color text not null default '#FFD60A',          -- accent used in the dashboard
  status text not null default 'paused' check (status in ('active','paused')),
  blocked_reason text,                           -- set by worker when a dependency is down
  posting_mode text not null default 'draft' check (posting_mode in ('draft','private','public')),
  require_approval boolean not null default true,
  posts_per_day int not null default 1 check (posts_per_day between 0 and 6),
  post_times text[] not null default '{"12:30","19:30"}',  -- HH:MM in timezone
  timezone text not null default 'America/New_York',
  buffer_days int not null default 1 check (buffer_days between 0 and 7),
  min_seconds int not null default 65 check (min_seconds >= 61),
  max_seconds int not null default 95,
  style jsonb not null default '{}',
  voice jsonb not null default '{}',
  content jsonb not null default '{}',           -- audience, pillars, hook styles, tone, hashtags, rules
  strategy jsonb not null default '{}',          -- maintained by the weekly brain
  tiktok_account_id uuid references public.tiktok_accounts(id) on delete set null,
  sort int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_ch_upd before update on public.channels for each row execute function touch_updated_at();
create unique index channels_one_account on public.channels(tiktok_account_id) where tiktok_account_id is not null;

-- ---------- ideas ----------
create table public.ideas (
  id uuid primary key default gen_random_uuid(),
  channel_id uuid not null references public.channels(id) on delete cascade,
  title text not null,
  angle text,                                   -- e.g. 'why' | 'trick' | channel-specific pillar
  pillar text,
  hook text,
  summary text,
  sources jsonb not null default '[]',
  keywords text[] not null default '{}',
  score numeric not null default 0,
  scores jsonb not null default '{}',           -- interest, search, novelty, fit, past_performance
  status text not null default 'new' check (status in ('new','queued','used','rejected','retired')),
  origin text not null default 'seed' check (origin in ('seed','research','review','manual')),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_idea_upd before update on public.ideas for each row execute function touch_updated_at();
create index ideas_channel_status on public.ideas(channel_id, status, score desc);

-- ---------- videos ----------
create table public.videos (
  id uuid primary key default gen_random_uuid(),
  channel_id uuid not null references public.channels(id) on delete cascade,
  idea_id uuid references public.ideas(id) on delete set null,
  title text not null default '',
  status text not null default 'queued' check (status in (
    'queued','researching','scripting','fact_checking','visuals','voice','rendering',
    'ready','approved','scheduled','uploading','sent_to_drafts','posted','rejected','failed','blocked')),
  stage_detail text,
  progress int not null default 0 check (progress between 0 and 100),
  error text,
  attempts int not null default 0,
  script jsonb,
  script_version int not null default 0,
  scorecard jsonb,
  factcheck jsonb,
  research jsonb,
  caption text,
  hashtags text[] not null default '{}',
  duration_s numeric,
  video_path text,           -- storage path in bucket 'videos'
  thumb_path text,           -- storage path in bucket 'videos'
  audio_path text,
  file_size bigint,
  cost_usd numeric not null default 0,
  cost_breakdown jsonb not null default '{}',
  experiment jsonb,          -- the one variable this video tests
  approval text check (approval in ('pending','approved','rejected')),
  approved_at timestamptz,
  rejection_note text,
  scheduled_for timestamptz,
  posted_at timestamptz,
  tiktok_publish_id text,
  tiktok_video_id text,
  tiktok_url text,
  publish_status jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_vid_upd before update on public.videos for each row execute function touch_updated_at();
create index videos_channel_status on public.videos(channel_id, status);
create index videos_sched on public.videos(scheduled_for) where status in ('approved','scheduled','ready');
create index videos_posted on public.videos(channel_id, posted_at desc);

create table public.video_stats (
  id bigserial primary key,
  video_id uuid not null references public.videos(id) on delete cascade,
  captured_at timestamptz not null default now(),
  source text not null default 'api' check (source in ('api','import')),
  views bigint, likes bigint, comments bigint, shares bigint, saves bigint,
  avg_watch_s numeric, completion_rate numeric, follows int,
  raw jsonb
);
create index video_stats_vid on public.video_stats(video_id, captured_at desc);

create table public.account_stats (
  id bigserial primary key,
  tiktok_account_id uuid not null references public.tiktok_accounts(id) on delete cascade,
  captured_at timestamptz not null default now(),
  follower_count int, likes_count bigint, video_count int
);
create index account_stats_acc on public.account_stats(tiktok_account_id, captured_at desc);

-- ---------- jobs (work queue) ----------
create table public.jobs (
  id bigserial primary key,
  type text not null,
  payload jsonb not null default '{}',
  status text not null default 'queued' check (status in ('queued','running','done','failed','cancelled','waiting')),
  priority int not null default 5,
  attempts int not null default 0,
  max_attempts int not null default 3,
  run_after timestamptz not null default now(),
  dedupe_key text,
  locked_by text,
  locked_at timestamptz,
  waiting_on text,                 -- service name the job is waiting for (credits/outage)
  last_error text,
  result jsonb,
  channel_id uuid references public.channels(id) on delete cascade,
  video_id uuid references public.videos(id) on delete cascade,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
create unique index jobs_dedupe on public.jobs(dedupe_key) where dedupe_key is not null and status in ('queued','running','waiting');
create index jobs_claim on public.jobs(status, run_after, priority);

-- claim the next runnable job atomically (SKIP LOCKED) — called by workers through PostgREST RPC
create or replace function public.claim_job(p_worker text, p_types text[] default null)
returns setof public.jobs language plpgsql security definer set search_path = public as $$
declare j public.jobs;
begin
  -- recover jobs whose worker died (locked > 45 min)
  update public.jobs set status = 'queued', locked_by = null, locked_at = null
   where status = 'running' and locked_at < now() - interval '45 minutes';

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

-- ---------- observability ----------
create table public.events (
  id bigserial primary key,
  level text not null default 'info' check (level in ('debug','info','warn','error','success')),
  scope text not null default 'system',
  message text not null,
  data jsonb,
  channel_id uuid references public.channels(id) on delete cascade,
  video_id uuid references public.videos(id) on delete cascade,
  created_at timestamptz not null default now()
);
create index events_time on public.events(created_at desc);
create index events_channel on public.events(channel_id, created_at desc);

create table public.services (
  name text primary key,           -- anthropic | elevenlabs | runpod | tiktok | storage | worker
  status text not null default 'unconfigured' check (status in ('ok','warning','down','out_of_credits','unconfigured')),
  message text,
  balance numeric,
  balance_unit text,
  balance_limit numeric,
  details jsonb not null default '{}',
  checked_at timestamptz,
  updated_at timestamptz not null default now()
);
create trigger trg_srv_upd before update on public.services for each row execute function touch_updated_at();
insert into public.services(name) values ('anthropic'),('elevenlabs'),('runpod'),('tiktok'),('storage'),('worker');

create table public.spend (
  id bigserial primary key,
  service text not null,
  amount_usd numeric not null default 0,
  units numeric,
  unit text,
  detail text,
  channel_id uuid references public.channels(id) on delete set null,
  video_id uuid references public.videos(id) on delete set null,
  created_at timestamptz not null default now()
);
create index spend_time on public.spend(created_at desc);

create table public.worker_heartbeats (
  worker_id text primary key,
  version text,
  host text,
  info jsonb not null default '{}',
  started_at timestamptz not null default now(),
  last_seen timestamptz not null default now()
);

create table public.settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);
create trigger trg_set_upd before update on public.settings for each row execute function touch_updated_at();

create table public.secrets (
  key text primary key,            -- anthropic_api_key, elevenlabs_api_key, runpod_api_key, tiktok_client_key, tiktok_client_secret, resend_api_key
  ciphertext text not null,
  hint text,                       -- last 4 chars, for display only
  updated_at timestamptz not null default now()
);

create table public.reports (
  id uuid primary key default gen_random_uuid(),
  channel_id uuid references public.channels(id) on delete cascade,
  kind text not null default 'weekly',
  period_start date not null,
  period_end date not null,
  title text not null,
  summary_md text not null,
  data jsonb not null default '{}',
  changes jsonb not null default '[]',
  created_at timestamptz not null default now()
);
create index reports_time on public.reports(created_at desc);

create table public.oauth_states (
  state text primary key,
  code_verifier text not null,
  channel_id uuid references public.channels(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- ---------- RLS ----------
do $$
declare t text;
begin
  foreach t in array array['admins','tiktok_accounts','channels','ideas','videos','video_stats','account_stats',
                           'jobs','events','services','spend','worker_heartbeats','settings','reports','secrets','oauth_states']
  loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
  foreach t in array array['channels','ideas','videos','video_stats','account_stats','jobs','events','services',
                           'spend','worker_heartbeats','settings','reports']
  loop
    execute format('create policy admin_all on public.%I for all to authenticated using (public.is_admin()) with check (public.is_admin())', t);
  end loop;
end $$;
create policy admin_read_self on public.admins for select to authenticated using (user_id = auth.uid());
-- tiktok_accounts: admins may read non-secret columns only (tokens are revoked at column level)
create policy admin_read on public.tiktok_accounts for select to authenticated using (public.is_admin());
create policy admin_update on public.tiktok_accounts for update to authenticated using (public.is_admin()) with check (public.is_admin());
revoke select (access_token_enc, refresh_token_enc) on public.tiktok_accounts from authenticated, anon;
revoke update (access_token_enc, refresh_token_enc, open_id) on public.tiktok_accounts from authenticated, anon;

-- ---------- realtime ----------
alter publication supabase_realtime add table public.videos, public.jobs, public.events, public.services, public.channels, public.worker_heartbeats;

-- ---------- storage ----------
insert into storage.buckets (id, name, public, file_size_limit)
values ('videos','videos', false, 524288000), ('backups','backups', false, 1073741824)
on conflict (id) do nothing;
create policy admin_read_videos on storage.objects for select to authenticated
  using (bucket_id = 'videos' and public.is_admin());

-- ---------- default settings ----------
insert into public.settings(key, value) values
  ('global', '{"paused": false, "auto_publish": false, "model": "claude-opus-5-5", "effort": "high", "daily_budget_usd": 15, "monthly_budget_usd": 300, "video_retention_days": 21, "report_email": null}'),
  ('anthropic_credit', '{"balance_usd": null, "set_at": null}');
