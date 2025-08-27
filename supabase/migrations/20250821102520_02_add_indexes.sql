-- Indexes for notes

-- Filter indexes to speed up common predicates
create index if not exists idx_notes_user_created_at on public.notes (user_id, created_at desc);
create index if not exists idx_notes_user_type on public.notes (user_id, note_type);
create index if not exists idx_notes_user_archived on public.notes (user_id, is_archived);

-- FTS index on lexeme
create index if not exists idx_notes_lexeme_gin on public.notes using gin (lexeme);

-- HNSW index for vector similarity search
-- Parameters: m=16 (default), ef_construction=64 (default)
-- For personal notes: these defaults work well for up to ~100k notes
-- For larger datasets, consider: m=32, ef_construction=80
do $$
begin
  if not exists (
    select 1 from pg_indexes where schemaname = 'public' and indexname = 'idx_notes_embedding_hnsw'
  ) then
    create index idx_notes_embedding_hnsw on public.notes using hnsw (embedding extensions.vector_cosine_ops);
  end if;
end$$;


