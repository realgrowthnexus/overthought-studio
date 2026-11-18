-- exactly one owner, enforced by the database (complements the app-level /setup race guard)
create unique index if not exists admins_single_owner on public.admins ((true));
-- bind OAuth state to the admin who started it
alter table public.oauth_states add column if not exists admin_id uuid references auth.users(id) on delete cascade;
