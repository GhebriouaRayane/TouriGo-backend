-- Upgrade script for mobile push notification tokens.

create table if not exists public.push_device_tokens (
  id bigserial primary key,
  user_id bigint not null references public.users(id) on delete cascade,
  token text not null,
  platform text not null,
  device_id text null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  constraint uq_push_device_tokens_token unique (token)
);

create index if not exists idx_push_device_tokens_user_id on public.push_device_tokens(user_id);
create index if not exists idx_push_device_tokens_platform on public.push_device_tokens(platform);
create index if not exists idx_push_device_tokens_device_id on public.push_device_tokens(device_id);
create index if not exists idx_push_device_tokens_is_active on public.push_device_tokens(is_active);
