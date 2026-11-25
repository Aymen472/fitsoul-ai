-- FitSoul AI Initial Supabase Postgres Schema (Module 1.5)
-- Enables pgvector for semantic memory (Phase 2) and Row-Level Security across all tables.

create extension if not exists "pgcrypto";
create extension if not exists "vector";

create table if not exists public.users (
    id text primary key default gen_random_uuid()::text,
    email text unique,
    full_name text,
    phone text unique,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.profiles (
    user_id text primary key references public.users(id) on delete cascade,
    age integer not null check (age between 18 and 80),
    gender text not null check (gender in ('female', 'male')),
    height_cm double precision not null check (height_cm between 120 and 220),
    weight_kg double precision not null check (weight_kg between 30 and 250),
    target_weight_kg double precision check (target_weight_kg between 30 and 250),
    target_date date,
    activity_level text not null,
    goal text not null check (goal in ('lose', 'maintain', 'gain')),
    conditions jsonb not null default '[]'::jsonb,
    high_risk_conditions jsonb not null default '[]'::jsonb,
    is_pregnant boolean not null default false,
    on_regular_medication boolean not null default false,
    diet_type text not null default 'non_veg',
    allergies jsonb not null default '[]'::jsonb,
    dislikes jsonb not null default '[]'::jsonb,
    timezone text not null default 'Asia/Karachi',
    wake_time time,
    sleep_time time,
    workout_time time,
    bmi double precision not null,
    is_high_risk boolean not null default false,
    high_risk_reasons jsonb not null default '[]'::jsonb,
    supplements_allowed boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.nutrition_targets (
    user_id text primary key references public.users(id) on delete cascade,
    calories integer not null,
    bmr integer not null,
    tdee integer not null,
    protein_g integer not null,
    carbs_g integer not null,
    fat_g integer not null,
    fiber_g integer not null,
    water_ml integer not null,
    sodium_mg_max integer not null,
    max_carbs_per_meal_g integer,
    forbidden_tags jsonb not null default '[]'::jsonb,
    required_tags jsonb not null default '[]'::jsonb,
    applied_rules jsonb not null default '[]'::jsonb,
    warnings jsonb not null default '[]'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists public.foods (
    id text primary key,
    name text not null,
    urdu_name text not null default '',
    aliases jsonb not null default '[]'::jsonb,
    category text not null,
    serving_desc text not null,
    grams double precision not null,
    kcal double precision not null,
    protein double precision not null,
    carbs double precision not null,
    fat double precision not null,
    fiber double precision not null,
    sodium_mg double precision not null,
    gi_category text not null default 'medium',
    tags jsonb not null default '[]'::jsonb
);

create table if not exists public.meal_logs (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    meal_type text not null,
    items jsonb not null default '[]'::jsonb,
    total_kcal double precision not null,
    protein_g double precision not null,
    carbs_g double precision not null,
    fat_g double precision not null,
    photo_url text,
    logged_at timestamptz not null default now()
);

create table if not exists public.water_logs (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    amount_ml integer not null check (amount_ml > 0),
    logged_at timestamptz not null default now()
);

create table if not exists public.weight_logs (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    weight_kg double precision not null check (weight_kg between 30 and 250),
    logged_at timestamptz not null default now()
);

create table if not exists public.workouts (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    routine_name text not null,
    workout_type text not null default 'fitness',
    duration_minutes integer not null check (duration_minutes > 0),
    calories_burned double precision not null default 0,
    completed_at timestamptz not null default now()
);

create table if not exists public.mood_logs (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    mood text not null,
    note text,
    logged_at timestamptz not null default now()
);

create table if not exists public.messages (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null,
    channel text not null default 'web',
    flagged_safety boolean not null default false,
    embedding vector(768),
    created_at timestamptz not null default now()
);

create table if not exists public.subscriptions (
    id text primary key default gen_random_uuid()::text,
    user_id text not null unique references public.users(id) on delete cascade,
    plan text not null default 'trial',
    status text not null default 'active',
    provider text,
    starts_at timestamptz not null default now(),
    expires_at timestamptz,
    created_at timestamptz not null default now()
);

-- Indexes
create index if not exists idx_meal_logs_user_logged_at
    on public.meal_logs (user_id, logged_at desc);
create index if not exists idx_water_logs_user_logged_at
    on public.water_logs (user_id, logged_at desc);
create index if not exists idx_weight_logs_user_logged_at
    on public.weight_logs (user_id, logged_at desc);
create index if not exists idx_messages_user_created_at
    on public.messages (user_id, created_at desc);
create index if not exists idx_foods_category
    on public.foods (category);

-- Row-Level Security (RLS)
alter table public.users enable row level security;
alter table public.profiles enable row level security;
alter table public.nutrition_targets enable row level security;
alter table public.foods enable row level security;
alter table public.meal_logs enable row level security;
alter table public.water_logs enable row level security;
alter table public.weight_logs enable row level security;
alter table public.workouts enable row level security;
alter table public.mood_logs enable row level security;
alter table public.messages enable row level security;
alter table public.subscriptions enable row level security;

create policy "users_own_row" on public.users
    for all using (auth.uid()::text = id) with check (auth.uid()::text = id);

create policy "profiles_own_rows" on public.profiles
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "nutrition_targets_own_rows" on public.nutrition_targets
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "foods_authenticated_read" on public.foods
    for select to authenticated using (true);

create policy "meal_logs_own_rows" on public.meal_logs
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "water_logs_own_rows" on public.water_logs
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "weight_logs_own_rows" on public.weight_logs
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "workouts_own_rows" on public.workouts
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "mood_logs_own_rows" on public.mood_logs
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "messages_own_rows" on public.messages
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "subscriptions_own_rows" on public.subscriptions
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
