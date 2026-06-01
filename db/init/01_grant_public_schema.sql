-- PostgreSQL 15+ revoked CREATE on the public schema from all roles by default.
-- This restores it for the app user so Alembic and the application can create tables.
GRANT CREATE ON SCHEMA public TO admin;
