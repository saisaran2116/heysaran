CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  password text,
  google_sub text UNIQUE,
  role text NOT NULL DEFAULT 'member' CHECK (role IN ('member','admin')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS plans (
  id text PRIMARY KEY,
  name text NOT NULL
);
INSERT INTO plans VALUES ('free','Free'), ('supporter','Supporter') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS memberships (
  account_id uuid PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
  plan_id text NOT NULL REFERENCES plans(id),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS usage_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  model text NOT NULL,
  input_tokens integer NOT NULL,
  output_tokens integer NOT NULL,
  estimated_usd numeric(14,8),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_account_date ON usage_events(account_id, created_at DESC);
CREATE TABLE IF NOT EXISTS stripe_events (
  id text PRIMARY KEY,
  received_at timestamptz NOT NULL DEFAULT now()
);
