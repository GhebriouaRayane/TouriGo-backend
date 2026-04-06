-- Upgrade script for carpool seat reservations.
-- Run once in Supabase SQL Editor.

begin;

alter table if exists public.bookings
  add column if not exists seats_reserved integer;

alter table if exists public.bookings
  drop constraint if exists ck_bookings_seats_reserved_positive;

alter table if exists public.bookings
  add constraint ck_bookings_seats_reserved_positive
  check (seats_reserved is null or seats_reserved > 0);

commit;
