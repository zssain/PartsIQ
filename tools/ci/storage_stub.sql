-- DISPOSABLE CI DATABASES ONLY. The bare supabase/postgres image has the auth schema but not
-- the Storage service's tables, which supabase/migrations/*_storage.sql attaches policies to.
-- This creates the two tables those policies need; a real Supabase project already has them.
CREATE SCHEMA IF NOT EXISTS storage;
CREATE TABLE IF NOT EXISTS storage.buckets (id text PRIMARY KEY, name text, public boolean, file_size_limit bigint, allowed_mime_types text[]);
CREATE TABLE IF NOT EXISTS storage.objects (id uuid DEFAULT gen_random_uuid() PRIMARY KEY, bucket_id text, name text, owner uuid);
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
GRANT ALL ON SCHEMA storage TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA storage TO postgres;
