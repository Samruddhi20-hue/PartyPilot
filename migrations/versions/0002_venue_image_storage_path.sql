-- PartyPilot migration 0002
BEGIN;
ALTER TABLE venue_images ADD COLUMN IF NOT EXISTS storage_path VARCHAR(500);
COMMIT;
