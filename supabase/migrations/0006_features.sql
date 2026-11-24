-- 0006: owner features (2026-11-24). Additive only.

-- Cover = a frame of the video (TikTok's API only takes a frame timestamp), picked on the video page.
alter table public.videos add column if not exists cover_ms int;
-- A post time the owner set by hand. The scheduler never moves or overwrites a locked time.
alter table public.videos add column if not exists schedule_locked boolean not null default false;

-- The dashboard assistant's conversation. The worker writes the replies; the dashboard reads them (admin only).
create table if not exists public.assistant_messages (
  id bigserial primary key,
  role text not null check (role in ('user', 'assistant')),
  content text not null default '',
  actions jsonb not null default '[]',
  status text not null default 'done' check (status in ('pending', 'done', 'error')),
  created_at timestamptz not null default now()
);
create index if not exists assistant_messages_created on public.assistant_messages(created_at desc);
alter table public.assistant_messages enable row level security;
drop policy if exists admin_all on public.assistant_messages;
create policy admin_all on public.assistant_messages for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
alter publication supabase_realtime add table public.assistant_messages;
