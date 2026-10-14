-- Offline-only histogram cache for anonymized mock-application score bands.
-- Never store person IDs, raw score profiles, IP addresses, or contacts here.
-- Execute manually in your own Supabase project after privacy/security review.
CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS private.mock_support_score_buckets (
  year smallint NOT NULL CHECK (year BETWEEN 2022 AND 2027),
  exam_type text NOT NULL CHECK (exam_type IN ('june','september','csat')),
  program_key text NOT NULL,
  score_bucket integer NOT NULL,
  bucket_width integer NOT NULL CHECK (bucket_width >= 1),
  participant_count bigint NOT NULL DEFAULT 0 CHECK (participant_count >= 0),
  source_kind text NOT NULL DEFAULT 'self_reported_mock_support',
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (year, exam_type, program_key, score_bucket, bucket_width)
);
ALTER TABLE private.mock_support_score_buckets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON private.mock_support_score_buckets FROM PUBLIC, anon, authenticated;
-- No anon/authenticated policies: client applications cannot read/write this table.
-- A trusted Edge Function should validate consent and score input, rate-limit,
-- compute the programme converted-score bucket, and atomically update counts.
-- Publish only sufficiently large, coarsened groups; no raw submissions.
