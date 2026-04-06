-- Upgrade script for immobilier room/guest reservations.
-- Run once in Supabase SQL Editor.

begin;

alter table if exists public.bookings
  add column if not exists rooms_reserved integer;

alter table if exists public.bookings
  add column if not exists guests_reserved integer;

alter table if exists public.bookings
  drop constraint if exists ck_bookings_rooms_reserved_positive;

alter table if exists public.bookings
  add constraint ck_bookings_rooms_reserved_positive
  check (rooms_reserved is null or rooms_reserved > 0);

alter table if exists public.bookings
  drop constraint if exists ck_bookings_guests_reserved_positive;

alter table if exists public.bookings
  add constraint ck_bookings_guests_reserved_positive
  check (guests_reserved is null or guests_reserved > 0);

commit;
