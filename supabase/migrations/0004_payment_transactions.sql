-- FitSoul AI Payment Transactions Audit Table (Module 5.1)
-- Tracks checkout sessions and webhook payment outcomes across Safepay, PayFast,
-- JazzCash, Easypaisa, and LemonSqueezy.

create table if not exists public.payment_transactions (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(id) on delete cascade,
    plan text not null,
    provider text not null,
    amount double precision not null,
    currency text not null default 'PKR',
    status text not null default 'pending' check (status in ('pending', 'paid', 'failed', 'refunded')),
    provider_order_id text not null unique,
    checkout_url text,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    paid_at timestamptz
);

create index if not exists idx_payment_tx_user_created_at
    on public.payment_transactions (user_id, created_at desc);

create index if not exists idx_payment_tx_order_id
    on public.payment_transactions (provider_order_id);

alter table public.payment_transactions enable row level security;

create policy "payment_transactions_own_rows" on public.payment_transactions
    for select using (auth.uid()::text = user_id);
