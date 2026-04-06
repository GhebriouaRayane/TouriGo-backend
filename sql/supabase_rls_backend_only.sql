-- Supabase RLS hardening for backend-only architecture.
-- Context: frontend does NOT call Supabase directly; only FastAPI talks to Postgres.
-- Result: PostgREST client roles (anon/authenticated) cannot access business tables.

begin;

alter table if exists public.users enable row level security;
alter table if exists public.listings enable row level security;
alter table if exists public.listing_images enable row level security;
alter table if exists public.bookings enable row level security;
alter table if exists public.reviews enable row level security;
alter table if exists public.favorites enable row level security;
alter table if exists public.messages enable row level security;
alter table if exists public.notifications enable row level security;
alter table if exists public.registration_codes enable row level security;

-- Optional defense in depth: remove direct table grants from API roles.
revoke all privileges on table public.users from anon, authenticated;
revoke all privileges on table public.listings from anon, authenticated;
revoke all privileges on table public.listing_images from anon, authenticated;
revoke all privileges on table public.bookings from anon, authenticated;
revoke all privileges on table public.reviews from anon, authenticated;
revoke all privileges on table public.favorites from anon, authenticated;
revoke all privileges on table public.messages from anon, authenticated;
revoke all privileges on table public.notifications from anon, authenticated;
revoke all privileges on table public.registration_codes from anon, authenticated;

commit;
