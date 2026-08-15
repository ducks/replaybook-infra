BEGIN;
ALTER TABLE staff_exports ADD COLUMN IF NOT EXISTS artifact_key text;
ALTER TABLE staff_exports ADD COLUMN IF NOT EXISTS completed_at timestamptz;
INSERT INTO schema_migrations (version) VALUES ('202608140001') ON CONFLICT DO NOTHING;
COMMIT;
