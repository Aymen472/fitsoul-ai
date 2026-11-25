-- FitSoul AI Long-Term Semantic Memory Table (Module 2.6)
-- Stores extracted preferences, triggers, wins, and lifestyle facts with pgvector embeddings.

create table if not exists public.user_memories (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    category text not null check (category in ('preference', 'trigger', 'win', 'fact')),
    content text not null,
    embedding vector(768),
    created_at timestamptz not null default now()
);

create index if not exists idx_user_memories_user_created_at
    on public.user_memories (user_id, created_at desc);

alter table public.user_memories enable row level security;

create policy "user_memories_own_rows" on public.user_memories
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
