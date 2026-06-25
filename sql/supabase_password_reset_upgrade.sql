-- Upgrade script for password reset OTP verification.
-- Run once in Supabase SQL Editor.

begin;

create table if not exists public.password_reset_codes (
  id bigserial primary key,
  email text not null,
  hashed_code text not null,
  attempts integer not null default 0,
  expires_at timestamptz not null,
  consumed_at timestamptz null,
  created_at timestamptz not null default now()
);

create index if not exists idx_password_reset_codes_email on public.password_reset_codes(email);
create index if not exists idx_password_reset_codes_expires_at on public.password_reset_codes(expires_at);
create index if not exists idx_password_reset_codes_consumed_at on public.password_reset_codes(consumed_at);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ck_password_reset_codes_attempts_non_negative'
  ) then
    alter table public.password_reset_codes
      add constraint ck_password_reset_codes_attempts_non_negative
      check (attempts >= 0);
  end if;
end
$$;

commit;
