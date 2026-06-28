-- AlterEgo quiz logging. No PII: identity is a salted SHA-256 hash of the IP.
-- One row per quiz submission, for distribution / health analysis.

create table if not exists quiz_logs (
  id           uuid primary key default gen_random_uuid(),
  created_at   timestamptz not null default now(),
  franchise    text not null,
  answers      jsonb not null,          -- { "q1": 5, "q2": 2, ... }
  trait_scores jsonb not null,          -- computed OCEAN 0-100
  match        text not null,           -- closest character
  runners_up   jsonb,                   -- [{ name, distance, similarity }, ...]
  distance     double precision,        -- distance to the closest character
  ip_hash      text                     -- salted SHA-256 of client IP, no raw PII
);

create index if not exists quiz_logs_franchise_idx on quiz_logs (franchise);
create index if not exists quiz_logs_created_at_idx on quiz_logs (created_at);

-- Inserts happen server-side via the service-role key only.
-- Keep row level security on with no public policies so anon/auth clients can't read or write.
alter table quiz_logs enable row level security;
