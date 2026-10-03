-- Run in Supabase SQL Editor. Supabase Auth owns user credentials.
create table if not exists public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  name text not null,
  age integer not null check (age between 13 and 110),
  height_cm numeric not null check (height_cm > 80 and height_cm <= 250),
  weight_kg numeric not null check (weight_kg > 25 and weight_kg <= 350),
  activity_level text not null check (activity_level in ('low','moderate','high')),
  dietary_preference text not null check (dietary_preference in ('vegetarian','vegan','general')),
  goal text not null check (goal in ('balanced','weight_management','fitness')),
  allergies text[] not null default '{}',
  created_at timestamptz not null default now()
);
create table if not exists public.diet_plans (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  breakfast text not null, lunch text not null, snack text not null, dinner text not null,
  nutrition_summary text not null, hydration_reminder text not null,
  educational_notice text not null, source text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.user_files (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  storage_path text not null unique,
  uploaded_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
alter table public.diet_plans enable row level security;
alter table public.user_files enable row level security;
create policy "Users manage own profile" on public.profiles for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage own plans" on public.diet_plans for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage own file metadata" on public.user_files for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('user-files', 'user-files', false, 5242880, array['image/jpeg','image/png','image/webp'])
on conflict (id) do nothing;
create policy "Users access own objects" on storage.objects for all
using (bucket_id = 'user-files' and (storage.foldername(name))[1] = auth.uid()::text)
with check (bucket_id = 'user-files' and (storage.foldername(name))[1] = auth.uid()::text);
