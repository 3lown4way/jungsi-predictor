-- Apply this with Supabase SQL Editor, not through public website.
-- Verified 2022-2026 September report cards paired with actual admissions.
-- Only database administrators using service_role may read.
create table if not exists public.historical_mock_outcomes (
  id bigint generated always as identity primary key,
  year integer not null check(year between 2022 and 2026),
  exam_type text not null check(exam_type='september'),
  program_key text not null,
  applicant_hash text not null check(length(applicant_hash)>=16),
  applied boolean not null default false check(applied=true),
  verified boolean not null default false check(verified=true),
  consented boolean not null default false check(consented=true),
  admitted integer not null check(admitted in (0,1)),
  student jsonb not null check(jsonb_typeof(student)='object'),
  created_at timestamptz not null default now(),
  unique(year,program_key,applicant_hash)
);
alter table public.historical_mock_outcomes enable row level security;
revoke all on public.historical_mock_outcomes from anon, authenticated;
revoke all on public.historical_mock_outcomes_id_seq from anon, authenticated;
grant select,insert,update,delete on public.historical_mock_outcomes to service_role;
grant usage,select on sequence public.historical_mock_outcomes_id_seq to service_role;
-- No RLS policies granted to anon/authenticated. Service-role API is server-side only.
