-- TRADELINE Legal Intelligence: PostgreSQL schema v2. Requires pgvector.
-- STATUS: written, NOT executed against PostgreSQL in the build environment (none available). Run it on a test database first.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE source_registry (            -- mirrors legal-api/sources/registry.json
  source_key text PRIMARY KEY, name text NOT NULL, tier smallint NOT NULL CHECK (tier IN (1,2,3)),
  authenticity text NOT NULL, evidence_allowed boolean NOT NULL, automation text NOT NULL,
  verified_on date NOT NULL, verified_status text NOT NULL,
  CHECK (NOT (tier = 3 AND evidence_allowed))
);

CREATE TABLE act (
  doc_id text PRIMARY KEY,                -- 'eurlex:32026R0382', 'sejm:DU/2020/1'
  jurisdiction text NOT NULL, title text NOT NULL, publisher text NOT NULL,
  source_key text NOT NULL REFERENCES source_registry(source_key)
);

CREATE TABLE act_version (                -- every version is kept; nothing is overwritten
  source_id text PRIMARY KEY, doc_id text NOT NULL REFERENCES act(doc_id),
  version_from date NOT NULL, version_to date,                    -- interval of this text version
  adopted_on date, published_on date, entered_into_force date,    -- the five legal dates stay separate
  applies_from date, ceases_on date,
  authenticity text NOT NULL DEFAULT 'official' CHECK (authenticity IN ('official','consolidated')),
  url text NOT NULL, full_text text NOT NULL, sha256 char(64) NOT NULL,
  original_blob_ref text,                -- the original file (HTML/PDF/XML) in object storage, same checksum
  retrieved_on date NOT NULL, ingestion_run bigint,
  CHECK (version_to IS NULL OR version_to >= version_from)
);
CREATE INDEX act_version_doc_dates ON act_version (doc_id, version_from);

CREATE TABLE act_relation (from_doc text NOT NULL REFERENCES act(doc_id), to_doc text NOT NULL, kind text NOT NULL,
  effective_on date, PRIMARY KEY (from_doc, to_doc, kind));

CREATE TABLE article_chunk (
  chunk_id bigserial PRIMARY KEY, source_id text NOT NULL REFERENCES act_version(source_id), article text, body text NOT NULL,
  embedding vector(1024), tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', body)) STORED
);
CREATE INDEX ON article_chunk USING gin (tsv);
CREATE INDEX ON article_chunk USING hnsw (embedding vector_cosine_ops);

CREATE TABLE ingestion_run (run_id bigserial PRIMARY KEY, source_key text NOT NULL, started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz, status text NOT NULL, fetched int DEFAULT 0, new_versions int DEFAULT 0, errors jsonb DEFAULT '[]');
CREATE TABLE change_event (event_id bigserial PRIMARY KEY, doc_id text NOT NULL, detected_at timestamptz NOT NULL DEFAULT now(),
  kind text NOT NULL, detail jsonb NOT NULL, reviewed boolean NOT NULL DEFAULT false);   -- feeds Legal Change Alerts

-- people, workspaces, research
CREATE TABLE app_user (user_id uuid PRIMARY KEY, email text UNIQUE NOT NULL, role text NOT NULL CHECK (role IN ('client','staff','reviewer','admin')),
  pw_hash text NOT NULL, email_verified boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE client_doc (doc_id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES app_user, name text NOT NULL, blob_ref text NOT NULL, text_extract text,
  sha256 char(64) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), delete_after date);
CREATE TABLE doc_grant (doc_id uuid REFERENCES client_doc, grantee_id uuid REFERENCES app_user, granted_by uuid NOT NULL, granted_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (doc_id, grantee_id));
CREATE TABLE research_run (run_id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app_user, params jsonb NOT NULL, as_of date NOT NULL,
  status text NOT NULL, report jsonb, model text, model_input_sha256 char(64), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE research_evidence (run_id uuid REFERENCES research_run, claim_no int, source_id text REFERENCES act_version, article text, quote text,
  verified boolean NOT NULL, reasons jsonb NOT NULL DEFAULT '[]', PRIMARY KEY (run_id, claim_no));   -- proves which exact version supported each claim
CREATE TABLE human_review (review_id bigserial PRIMARY KEY, run_id uuid NOT NULL REFERENCES research_run, reviewer_id uuid NOT NULL REFERENCES app_user,
  decision text NOT NULL CHECK (decision IN ('approved','changed','rejected')), comment text, decided_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE audit_log (id bigserial PRIMARY KEY, ts timestamptz NOT NULL DEFAULT now(), actor uuid, action text NOT NULL, object text, allowed boolean NOT NULL, ip inet);
CREATE TABLE job (job_id bigserial PRIMARY KEY, kind text NOT NULL, payload jsonb NOT NULL, run_after timestamptz NOT NULL DEFAULT now(), attempts int NOT NULL DEFAULT 0, state text NOT NULL DEFAULT 'queued');
  -- worker takes jobs with: SELECT ... FOR UPDATE SKIP LOCKED. No Redis or Celery in the MVP.

-- client isolation enforced by the database as a second barrier, not only by application code
ALTER TABLE client_doc ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_docs ON client_doc USING (owner_id = current_setting('app.user_id')::uuid
  OR EXISTS (SELECT 1 FROM doc_grant g WHERE g.doc_id = client_doc.doc_id AND g.grantee_id = current_setting('app.user_id')::uuid));
ALTER TABLE research_run ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_runs ON research_run USING (user_id = current_setting('app.user_id')::uuid);
-- the application sets: SET LOCAL app.user_id = '<uuid>' at the start of every request, and connects as a role without BYPASSRLS.
