-- Upgrade script for booking approval, notifications and messaging.
-- Run once in Supabase SQL Editor.

begin;

create table if not exists public.messages (
  id bigserial primary key,
  booking_id bigint not null references public.bookings(id) on delete cascade,
  sender_id bigint not null references public.users(id) on delete cascade,
  recipient_id bigint not null references public.users(id) on delete cascade,
  content text not null,
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_messages_booking_id on public.messages(booking_id);
create index if not exists idx_messages_sender_id on public.messages(sender_id);
create index if not exists idx_messages_recipient_id on public.messages(recipient_id);
create index if not exists idx_messages_created_at on public.messages(created_at);

create table if not exists public.notifications (
  id bigserial primary key,
  user_id bigint not null references public.users(id) on delete cascade,
  type text not null,
  title text not null,
  body text not null,
  is_read boolean not null default false,
  booking_id bigint null references public.bookings(id) on delete set null,
  message_id bigint null references public.messages(id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists idx_notifications_user_id on public.notifications(user_id);
create index if not exists idx_notifications_is_read on public.notifications(is_read);
create index if not exists idx_notifications_booking_id on public.notifications(booking_id);
create index if not exists idx_notifications_message_id on public.notifications(message_id);
create index if not exists idx_notifications_created_at on public.notifications(created_at);

commit;
