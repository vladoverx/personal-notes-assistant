-- RPCs for public search and agent search

create or replace function public.search_notes(
  p_query text default null,
  p_tags text[] default null,
  p_match_all_tags boolean default false,
  p_note_type public.note_type default null,
  p_is_archived boolean default null,
  p_limit int default 20
)
returns table (
  id uuid,
  title text,
  content text,
  note_type public.note_type,
  tags text[],
  user_id uuid,
  is_archived boolean,
  created_at timestamptz,
  updated_at timestamptz,
  rank real
)
language sql
stable
set search_path = public, extensions
as $$
  select n.id, n.title, n.content, n.note_type, n.tags, n.user_id, n.is_archived,
         n.created_at, n.updated_at,
         (case when p_query is null or length(trim(p_query)) = 0 then 0::real
               else ts_rank_cd(n.lexeme, websearch_to_tsquery('english', public.unaccent_immutable(p_query))) end)::real as rank
  from public.notes n
  where n.user_id = auth.uid()
    and (p_query is null or n.lexeme @@ websearch_to_tsquery('english', public.unaccent_immutable(p_query)))
    and (
      p_tags is null or (
        case when p_match_all_tags then n.tags @> p_tags else n.tags && p_tags end
      )
    )
    and (p_note_type is null or n.note_type = p_note_type)
    and (p_is_archived is null or n.is_archived = p_is_archived)
  order by rank desc nulls last, n.created_at desc
  limit greatest(1, least(p_limit, 200));
$$;

revoke all on function public.search_notes(text, text[], boolean, public.note_type, boolean, int) from public;
grant execute on function public.search_notes(text, text[], boolean, public.note_type, boolean, int) to authenticated;

create or replace function public.search_notes_agent(
  p_query text default null,
  p_query_embedding extensions.vector(1536) default null,
  p_tags text[] default null,
  p_match_all_tags boolean default false,
  p_note_type public.note_type default null,
  p_is_archived boolean default null,
  p_limit int default 20,
  p_alpha real default 0.5,
  p_created_from timestamptz default null,
  p_created_to timestamptz default null,
  p_updated_from timestamptz default null,
  p_updated_to timestamptz default null
)
returns table (
  id uuid,
  title text,
  content text,
  note_type public.note_type,
  tags text[],
  user_id uuid,
  is_archived boolean,
  created_at timestamptz,
  updated_at timestamptz,
  rank real
)
language plpgsql
stable
set search_path = public, extensions
as $$
begin
  return query
  with ranked as (
    select n.id, n.title, n.content, n.note_type, n.tags, n.user_id, n.is_archived,
           n.created_at, n.updated_at,
           -- Text score normalized (0..1 approx). If no query, score 0
           case when p_query is null or length(trim(p_query)) = 0 then 0
                else greatest(0, least(1, ts_rank_cd(n.lexeme, websearch_to_tsquery('english', public.unaccent_immutable(p_query))) * 2)) end as text_score,
           -- Vector similarity (cosine) converted to similarity (1 - distance). If no embedding, 0
           case when p_query_embedding is null or n.embedding is null then 0
                else 1 - (n.embedding <=> p_query_embedding) end as vector_score
    from public.notes n
    where n.user_id = auth.uid()
      and (p_query is null or n.lexeme @@ websearch_to_tsquery('english', public.unaccent_immutable(p_query)))
      and (
        p_tags is null or (
          case when p_match_all_tags then n.tags @> p_tags else n.tags && p_tags end
        )
      )
      and (p_note_type is null or n.note_type = p_note_type)
      and (p_is_archived is null or n.is_archived = p_is_archived)
      and (p_created_from is null or n.created_at >= p_created_from)
      and (p_created_to is null or n.created_at <= p_created_to)
      and (p_updated_from is null or n.updated_at >= p_updated_from)
      and (p_updated_to is null or n.updated_at <= p_updated_to)
  )
  select r.id, r.title, r.content, r.note_type, r.tags, r.user_id, r.is_archived,
         r.created_at, r.updated_at,
         (p_alpha * r.text_score + (1 - p_alpha) * r.vector_score) as rank
  from ranked r
  order by rank desc nulls last, r.created_at desc
  limit greatest(1, least(p_limit, 200));
end;
$$;

revoke all on function public.search_notes_agent(text, extensions.vector, text[], boolean, public.note_type, boolean, int, real, timestamptz, timestamptz, timestamptz, timestamptz) from public;
grant execute on function public.search_notes_agent(text, extensions.vector, text[], boolean, public.note_type, boolean, int, real, timestamptz, timestamptz, timestamptz, timestamptz) to authenticated;


