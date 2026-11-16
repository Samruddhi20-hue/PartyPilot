-- PartyPilot migration 0001
-- Adds booking form fields without dropping or rewriting existing data.
BEGIN;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS event_name VARCHAR(180);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS duration VARCHAR(30);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS organiser_name VARCHAR(120);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS company_name VARCHAR(180);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(20);
COMMIT;
