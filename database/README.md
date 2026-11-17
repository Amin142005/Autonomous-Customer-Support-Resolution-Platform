# PostgreSQL schema

The SQLAlchemy models in `backend/app/models/entities.py` are the portable
application model. `schema.sql` is the complete schema for a clean PostgreSQL or
Supabase database, and `rls_policies.sql` enables authenticated read-only access.
The API uses the Supabase `service_role` key on the server for all writes; never
expose that key to the frontend.

For a clean database, apply `schema.sql`, `rls_policies.sql`, and then `seed.sql`.
`seed.sql` is generated from the JSON fixtures with
`python database/generate_seed_sql.py`. To upgrade a database that already tracks
migrations, apply the numbered files under `migrations/` in order instead. Do not
apply both setup paths to the same database. Applied migrations are immutable;
create the next numbered migration for changes.

`schema.sql` and `rls_policies.sql` are also convenient for the Supabase SQL editor.
No live database credentials are required by the offline test suite.
