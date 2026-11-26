-- 0006: owner features (2026-11-26). Additive only.

-- Video page: the cover is one frame of the video (TikTok's API only takes a frame timestamp), and a post time the
-- owner sets by hand is locked so the scheduler never moves it.
alter table public.videos add column if not exists cover_ms int check (cover_ms is null or cover_ms >= 0);
alter table public.videos add column if not exists schedule_locked boolean not null default false;

-- AI assistant: the chat history. The dashboard writes the owner's messages, the worker writes the replies.
-- actions = proposed buttons; each one only runs when the owner clicks it.
create table if not exists public.assistant_messages (
  id bigint generated always as identity primary key,
  role text not null check (role in ('user', 'assistant')),
  content text not null default '',
  actions jsonb not null default '[]'::jsonb,
  status text not null default 'done' check (status in ('pending', 'done', 'error')),
  created_at timestamptz not null default now()
);
create index if not exists assistant_messages_created on public.assistant_messages (created_at desc);

alter table public.assistant_messages enable row level security;
drop policy if exists admin_all on public.assistant_messages;
create policy admin_all on public.assistant_messages for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

do $$
begin
  alter publication supabase_realtime add table public.assistant_messages;
exception when duplicate_object then null;
end $$;
