-- FitSoul AI WhatsApp Notification Preferences & Delivery Logs (Module 4.1)
-- Supports template-based proactive notifications (ADR-001), STOP/START opt-in state,
-- delivery status webhook updates, and per-user quiet hours.

create table if not exists public.notification_preferences (
    user_id text primary key references public.users(id) on delete cascade,
    whatsapp_opt_in boolean not null default false,
    whatsapp_phone text,
    meal_reminders boolean not null default true,
    water_reminders boolean not null default true,
    workout_reminders boolean not null default true,
    night_summary boolean not null default true,
    weekly_report boolean not null default true,
    quiet_hours_start text not null default '22:30',
    quiet_hours_end text not null default '07:00',
    updated_at timestamptz not null default now()
);

create table if not exists public.notification_logs (
    id text primary key default gen_random_uuid()::text,
    user_id text references public.users(id) on delete cascade,
    channel text not null default 'whatsapp',
    direction text not null check (direction in ('outbound', 'inbound')),
    template_name text,
    recipient_phone text not null,
    provider_message_id text,
    status text not null default 'queued',
    deep_link text,
    payload jsonb not null default '{}'::jsonb,
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_notification_prefs_phone
    on public.notification_preferences (whatsapp_phone);

create index if not exists idx_notification_logs_user_created_at
    on public.notification_logs (user_id, created_at desc);

create index if not exists idx_notification_logs_provider_msg_id
    on public.notification_logs (provider_message_id);

alter table public.notification_preferences enable row level security;
alter table public.notification_logs enable row level security;

create policy "notification_preferences_own_rows" on public.notification_preferences
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

create policy "notification_logs_own_rows" on public.notification_logs
    for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
