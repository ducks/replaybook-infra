BEGIN;
ALTER TABLE orders
  ADD COLUMN deployment_generation text NOT NULL DEFAULT 'legacy';
INSERT INTO schema_migrations (version) VALUES ('202608170001');
COMMIT;
