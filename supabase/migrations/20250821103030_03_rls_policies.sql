-- Enable RLS and define per-user policies

alter table public.notes enable row level security;

-- SELECT: owner can read
drop policy if exists "notes select" on public.notes;
create policy "notes select"
  on public.notes for select
  to authenticated
  using (auth.uid() = user_id);

-- INSERT: owner must be current user
drop policy if exists "notes insert" on public.notes;
create policy "notes insert"
  on public.notes for insert
  to authenticated
  with check (auth.uid() = user_id);

-- UPDATE: owner only
drop policy if exists "notes update" on public.notes;
create policy "notes update"
  on public.notes for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- DELETE: owner only
drop policy if exists "notes delete" on public.notes;
create policy "notes delete"
  on public.notes for delete
  to authenticated
  using (auth.uid() = user_id);


