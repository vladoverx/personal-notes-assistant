-- Enable required extensions for notes search and UUIDs

-- Create extensions schema first
create schema if not exists extensions;

create extension if not exists pgcrypto;           -- gen_random_uuid()
create extension if not exists vector with schema extensions;             -- pgvector for embeddings
create extension if not exists unaccent with schema extensions;           -- normalize text for FTS

