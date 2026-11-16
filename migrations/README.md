# PartyPilot database migrations

Apply SQL migrations to the Supabase PostgreSQL database in ascending order before deploying code that depends on the new columns.

Current migrations:
1. `versions/0001_booking_contact_fields.sql` — adds event name, duration and organiser contact fields to bookings.
2. `versions/0002_venue_image_storage_path.sql` — adds the storage object key to venue images.

Review each SQL file and take a database backup before applying it. These scripts are additive and do not drop existing data.

For a fresh database, create the current schema from `app/models.py` using a controlled initial schema process, then record which additive migrations have been applied. Do not run test fixtures or `drop_all()` against the production database.
