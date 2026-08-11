BEGIN;

ALTER TABLE moderation_jobs
  ADD COLUMN IF NOT EXISTS delivery_state text;

UPDATE moderation_jobs
SET delivery_state = CASE
  WHEN completed_at IS NULL THEN 'pending'
  ELSE 'completed'
END
WHERE delivery_state IS NULL;

ALTER TABLE moderation_jobs
  ALTER COLUMN delivery_state SET DEFAULT 'pending',
  ALTER COLUMN delivery_state SET NOT NULL;

INSERT INTO schema_migrations (version)
VALUES ('202608110001')
ON CONFLICT (version) DO NOTHING;

COMMIT;
