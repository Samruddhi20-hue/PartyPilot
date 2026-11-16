# PartyPilot

PartyPilot is a Flask-based event venue discovery and booking marketplace with customer, restaurant-partner and administrator portals.

## Stack

- Python / Flask
- Flask-SQLAlchemy and Flask-Login
- Supabase PostgreSQL
- Supabase Storage for venue images
- HTML, CSS and JavaScript
- Render deployment configuration

## Local setup

1. Use Python 3.11.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and fill in local development values. Do not commit `.env`.
5. Start the application:

   ```bash
   python run.py
   ```

6. Open `http://127.0.0.1:5000` and check `http://127.0.0.1:5000/health`.

## Environment variables

Set either `DATABASE_URL` or the individual `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME` variables.

For venue image uploads, configure server-side `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET`. Never put the service-role key in frontend code.

## Supabase Storage setup

Create a bucket named `venue-images` (or set `SUPABASE_STORAGE_BUCKET` to the chosen bucket). The implementation returns public image URLs, so enable public read access for the bucket. Upload and delete operations are performed by the Flask server using the service-role key; do not grant anonymous upload or delete permissions.

## Database migrations

Review and apply the SQL migrations under `migrations/versions/` to the Supabase PostgreSQL database in ascending order before deploying the code. Back up the database first. The migrations are additive and do not drop existing records.

## Create the first administrator

There is intentionally no public admin registration. After the database schema is ready, create an administrator from a trusted local shell:

```bash
flask --app app.py create-admin
```

The command prompts for the administrator name, email and a password (minimum 12 characters). Do not expose this command through a public web route.

## Tests

Run:

```bash
python -m pytest -q
```

Tests use an isolated in-memory SQLite database. They must never be configured to use the production Supabase database.

## Render

A `render.yaml` and `Procfile` are included. Set the production `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` in Render. Render generates `SECRET_KEY` from the blueprint configuration. Apply the SQL migrations before deploying code that relies on the new columns.

## Important security notes

- Rotate any database passwords or application secret keys that may have been exposed.
- Keep `.env`, `.venv`, local database files and credentials out of Git.
- Create the first administrator account through a controlled administrative process; public admin registration is intentionally not available.
- Payment processing is not implemented.
- Email-based password reset is not enabled until an email provider is configured.
