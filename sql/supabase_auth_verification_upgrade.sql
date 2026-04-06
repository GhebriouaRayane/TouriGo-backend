-- Upgrade script for registration OTP verification.
-- Run once in Supabase SQL Editor.

begin;

create table if not exists public.registration_codes (
  id bigserial primary key,
  email text not null,
  phone_number text null,
  full_name text null,
  avatar_url text null,
  hashed_password text not null,
  role text not null default 'user',
  channel text not null,
  hashed_code text not null,
  attempts integer not null default 0,
  expires_at timestamptz not null,
  consumed_at timestamptz null,
  created_at timestamptz not null default now()
);

create index if not exists idx_registration_codes_email on public.registration_codes(email);
create index if not exists idx_registration_codes_phone_number on public.registration_codes(phone_number);
create index if not exists idx_registration_codes_expires_at on public.registration_codes(expires_at);
create index if not exists idx_registration_codes_consumed_at on public.registration_codes(consumed_at);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ck_registration_codes_attempts_non_negative'
  ) then
    alter table public.registration_codes
      add constraint ck_registration_codes_attempts_non_negative
      check (attempts >= 0);
  end if;
end
$$;

commit;
