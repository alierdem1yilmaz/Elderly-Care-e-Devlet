-- Sahiplik: Kişi 1 (ali-erdem)
-- Supabase SQL Editor'de bu dosyanın tamamını çalıştırın (Project > SQL Editor > New query).
--
-- Not: Backend (FastAPI), service_role anahtarıyla bağlanır ve bu RLS
-- kurallarını BYPASS eder — asıl yetkilendirme backend/auth.py içindeki Python
-- kodunda yapılır. Buradaki RLS, gelecekte mobil app gibi istemcilerin
-- doğrudan Supabase'e bağlanması için ikinci bir savunma katmanıdır.

create extension if not exists "pgcrypto";

create table if not exists families (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now()
);

-- Bir Supabase Auth kullanıcısını (aile üyesi) bir aileye bağlar.
create table if not exists family_members (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references families(id) on delete cascade,
  auth_user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (auth_user_id)
);

-- Bakılan yaşlı kişi. phone_number, telefon aramalarında arayan numarayı
-- (caller ID) eşleştirmek için kullanılır — E.164 formatında olmalı (+905xxxxxxxxx).
--
-- family_id BİLEREK nullable: masaüstü uygulaması ilk açılışta kendi kendine
-- yerel bir kimlik (case_id == bu tablonun id'si) üretip hiçbir aileye
-- bağlanmadan kullanmaya başlıyor (bkz. backend/state.py::_fetch_case_row).
-- Kullanıcı daha sonra bir eşleştirme koduyla gerçek bir aileye bağlanınca
-- (POST /pair akışının tersi, aile tarafında yapılacak bir "claim" adımı)
-- bu satırın family_id'si doldurulur — geçmiş verisi kaybolmaz.
create table if not exists elderly_profiles (
  id uuid primary key default gen_random_uuid(),
  family_id uuid references families(id) on delete cascade,
  name text,
  phone_number text unique,
  created_at timestamptz not null default now()
);

-- backend/state.py'deki eski global in-memory _case dict'inin veritabanı karşılığı.
create table if not exists cases (
  id uuid primary key default gen_random_uuid(),
  elderly_profile_id uuid not null unique references elderly_profiles(id) on delete cascade,
  eligibility jsonb not null default '[]'::jsonb,
  checklist jsonb not null default '[]'::jsonb,
  notifications jsonb not null default '[]'::jsonb,
  appointments jsonb not null default '[]'::jsonb,
  profile jsonb,
  roadmap jsonb not null default '[]'::jsonb,
  next_step text,
  updated_at timestamptz not null default now()
);

-- Electron masaüstü uygulamasını bir aileye tek seferlik bağlamak için
-- kullanılan kısa ömürlü kod. Yaşlı kullanıcı hiçbir zaman gerçek bir
-- şifre/giriş ekranı görmez — sadece kurulumda bu kodu bir kere girer.
create table if not exists pairing_codes (
  code text primary key,
  elderly_profile_id uuid not null references elderly_profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '15 minutes'),
  used_at timestamptz
);

alter table families enable row level security;
alter table family_members enable row level security;
alter table elderly_profiles enable row level security;
alter table cases enable row level security;
alter table pairing_codes enable row level security;

create policy "family_members_select_own" on family_members
  for select using (auth_user_id = auth.uid());

create policy "families_select_own" on families
  for select using (
    id in (select family_id from family_members where auth_user_id = auth.uid())
  );

create policy "elderly_profiles_select_own_family" on elderly_profiles
  for select using (
    family_id in (select family_id from family_members where auth_user_id = auth.uid())
  );

create policy "elderly_profiles_insert_own_family" on elderly_profiles
  for insert with check (
    family_id in (select family_id from family_members where auth_user_id = auth.uid())
  );

create policy "cases_select_own_family" on cases
  for select using (
    elderly_profile_id in (
      select ep.id from elderly_profiles ep
      join family_members fm on fm.family_id = ep.family_id
      where fm.auth_user_id = auth.uid()
    )
  );
