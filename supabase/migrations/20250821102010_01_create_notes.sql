-- Create notes type(s), table and supporting objects

-- Create enum for note_type for data integrity (matches backend NoteType)
do $$
begin
  if not exists (
    select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
    where n.nspname = 'public' and t.typname = 'note_type'
  ) then
    create type public.note_type as enum (
      'note', 'task', 'event', 'recipe', 'vocabulary'
    );
  end if;
end$$;

-- Create immutable wrapper for unaccent function (required for generated columns)
create or replace function public.unaccent_immutable(text)
returns text
language sql
immutable
set search_path = ''
as $$ select extensions.unaccent($1) $$;

-- Create notes table
create table if not exists public.notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,

  title text,
  content text,
  note_type public.note_type not null default 'note',
  tags text[] default null,

  is_archived boolean not null default false,
  embedding extensions.vector(1536) default null,

  created_at timestamptz not null default now(),
  updated_at timestamptz,
  constraint notes_title_or_content_nonempty
    check ((title is not null and btrim(title) <> '') or (content is not null and btrim(content) <> '')),
  constraint notes_embedding_dimensions_check
    check (embedding is null or vector_dims(embedding) = 1536)
);

comment on column public.notes.embedding is 'Vector embedding for semantic search (1536 dimensions for OpenAI text-embedding-3-small). NULL when not yet generated.';

-- FTS column with weighting (A: title, B: content, C: tags), maintained via trigger
-- Using a trigger avoids immutability constraints on generated columns when using unaccent
alter table public.notes
  add column if not exists lexeme tsvector;

create or replace function public.notes_update_lexeme()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.lexeme :=
    setweight(to_tsvector('english', public.unaccent_immutable(coalesce(new.title, ''))), 'A') ||
    setweight(to_tsvector('english', public.unaccent_immutable(coalesce(new.content, ''))), 'B') ||
    setweight(to_tsvector('english', public.unaccent_immutable(coalesce(array_to_string(coalesce(new.tags, '{}'::text[]), ' '), ''))), 'C');
  return new;
end;
$$;

drop trigger if exists trg_notes_lexeme on public.notes;
create trigger trg_notes_lexeme
before insert or update of title, content, tags
on public.notes
for each row
execute function public.notes_update_lexeme();

-- updated_at trigger
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_notes_set_updated_at on public.notes;
create trigger trg_notes_set_updated_at
before update on public.notes
for each row
execute function public.set_updated_at();


