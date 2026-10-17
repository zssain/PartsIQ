-- PartsIQ initial schema.
-- Executed automatically by the postgres container on first initialisation (empty data volume).
-- Design principle: the database is the single source of truth for part compatibility.
-- AI components may rank and describe candidates, but never decide whether a part fits a machine.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ---------------------------------------------------------------------------
-- Shared trigger functions
-- ---------------------------------------------------------------------------

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Equipment catalogue
-- ---------------------------------------------------------------------------

CREATE TABLE equipment_families (
    id          SMALLSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_]{2,32}$'),
    name_en     TEXT NOT NULL,
    name_ar     TEXT NOT NULL
);

CREATE TABLE equipment_models (
    id            SERIAL PRIMARY KEY,
    family_id     SMALLINT NOT NULL REFERENCES equipment_families (id),
    brand         TEXT NOT NULL,
    model_code    TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    rated_output  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand, model_code)
);

CREATE INDEX equipment_models_model_code_trgm_idx
    ON equipment_models USING gin (model_code gin_trgm_ops);

-- A configuration is a serial-number range of a model that shares one bill of materials.
-- Overlapping ranges for the same model are rejected so serial lookup is always unambiguous.
CREATE TABLE model_configurations (
    id            SERIAL PRIMARY KEY,
    model_id      INTEGER NOT NULL REFERENCES equipment_models (id) ON DELETE CASCADE,
    config_code   TEXT NOT NULL,
    description   TEXT NOT NULL,
    serial_start  BIGINT NOT NULL CHECK (serial_start >= 0),
    serial_end    BIGINT NOT NULL,
    CHECK (serial_start <= serial_end),
    UNIQUE (model_id, config_code),
    EXCLUDE USING gist (
        model_id WITH =,
        int8range(serial_start, serial_end, '[]') WITH &&
    )
);

-- ---------------------------------------------------------------------------
-- Parts
-- ---------------------------------------------------------------------------

CREATE TABLE parts (
    id               SERIAL PRIMARY KEY,
    part_number      TEXT NOT NULL UNIQUE,
    name_en          TEXT NOT NULL,
    name_ar          TEXT NOT NULL,
    description_en   TEXT NOT NULL DEFAULT '',
    category         TEXT NOT NULL,
    unit_of_measure  TEXT NOT NULL DEFAULT 'EA',
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_document  TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'simple'::regconfig,
            part_number || ' ' || name_en || ' ' || name_ar || ' ' || description_en
        )
    ) STORED
);

CREATE INDEX parts_search_document_idx ON parts USING gin (search_document);
CREATE INDEX parts_part_number_trgm_idx ON parts USING gin (part_number gin_trgm_ops);
CREATE INDEX parts_category_idx ON parts (category);

CREATE TRIGGER parts_set_updated_at
    BEFORE UPDATE ON parts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Informal names used by customers and staff, e.g. "black filter" or Arabic colloquial terms.
CREATE TABLE part_aliases (
    id        SERIAL PRIMARY KEY,
    part_id   INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    alias     TEXT NOT NULL,
    language  TEXT NOT NULL CHECK (language IN ('en', 'ar')),
    UNIQUE (part_id, alias)
);

CREATE INDEX part_aliases_alias_trgm_idx ON part_aliases USING gin (alias gin_trgm_ops);

-- Embeddings are stored separately so the embedding model can be replaced without altering parts.
-- Dimension 1024 matches multilingual models such as BGE-M3, which support Arabic and English.
CREATE TABLE part_embeddings (
    part_id      INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    model_name   TEXT NOT NULL,
    source_text  TEXT NOT NULL,
    embedding    VECTOR(1024) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (part_id, model_name)
);

CREATE INDEX part_embeddings_hnsw_idx
    ON part_embeddings USING hnsw (embedding vector_cosine_ops);

-- The authoritative compatibility matrix. Every row must cite the document it was derived from.
CREATE TABLE part_compatibility (
    part_id            INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    configuration_id   INTEGER NOT NULL REFERENCES model_configurations (id) ON DELETE CASCADE,
    quantity_per_unit  NUMERIC(10, 3) NOT NULL DEFAULT 1 CHECK (quantity_per_unit > 0),
    source_reference   TEXT NOT NULL,
    notes              TEXT,
    PRIMARY KEY (part_id, configuration_id)
);

CREATE INDEX part_compatibility_configuration_idx ON part_compatibility (configuration_id);

-- Each superseded part has exactly one direct successor; chains are resolved by recursive query.
CREATE TABLE part_supersessions (
    old_part_id     INTEGER PRIMARY KEY REFERENCES parts (id) ON DELETE CASCADE,
    new_part_id     INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    effective_date  DATE NOT NULL,
    reason          TEXT,
    CHECK (old_part_id <> new_part_id)
);

CREATE INDEX part_supersessions_new_part_idx ON part_supersessions (new_part_id);

CREATE FUNCTION prevent_supersession_cycle() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        WITH RECURSIVE chain (part_id) AS (
            SELECT NEW.new_part_id
            UNION
            SELECT s.new_part_id
            FROM part_supersessions AS s
            JOIN chain AS c ON s.old_part_id = c.part_id
            WHERE s.old_part_id <> NEW.old_part_id
        )
        SELECT 1 FROM chain WHERE part_id = NEW.old_part_id
    ) THEN
        RAISE EXCEPTION 'Supersession % -> % would create a cycle', NEW.old_part_id, NEW.new_part_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER part_supersessions_no_cycles
    BEFORE INSERT OR UPDATE ON part_supersessions
    FOR EACH ROW EXECUTE FUNCTION prevent_supersession_cycle();

-- ---------------------------------------------------------------------------
-- Inventory
-- ---------------------------------------------------------------------------

CREATE TABLE warehouses (
    id      SMALLSERIAL PRIMARY KEY,
    code    TEXT NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_]{2,16}$'),
    name    TEXT NOT NULL,
    region  TEXT NOT NULL
);

CREATE TABLE stock_levels (
    part_id            INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    warehouse_id       SMALLINT NOT NULL REFERENCES warehouses (id) ON DELETE CASCADE,
    quantity_on_hand   INTEGER NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    quantity_reserved  INTEGER NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (part_id, warehouse_id),
    CHECK (quantity_reserved <= quantity_on_hand)
);

CREATE TRIGGER stock_levels_set_updated_at
    BEFORE UPDATE ON stock_levels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Enquiry workflow
-- ---------------------------------------------------------------------------

CREATE TYPE enquiry_status AS ENUM (
    'received',
    'processing',
    'needs_information',
    'awaiting_review',
    'approved',
    'rejected',
    'failed'
);

CREATE TABLE enquiries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel             TEXT NOT NULL CHECK (channel IN ('chat', 'email', 'staff')),
    customer_reference  TEXT,
    raw_text            TEXT NOT NULL,
    detected_language   TEXT CHECK (detected_language IN ('en', 'ar', 'mixed')),
    extracted           JSONB NOT NULL DEFAULT '{}'::jsonb,
    configuration_id    INTEGER REFERENCES model_configurations (id),
    status              enquiry_status NOT NULL DEFAULT 'received',
    failure_reason      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX enquiries_status_created_idx ON enquiries (status, created_at DESC);

CREATE TRIGGER enquiries_set_updated_at
    BEFORE UPDATE ON enquiries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE enquiry_attachments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enquiry_id   UUID NOT NULL REFERENCES enquiries (id) ON DELETE CASCADE,
    storage_key  TEXT NOT NULL UNIQUE,
    media_type   TEXT NOT NULL CHECK (media_type IN ('image/jpeg', 'image/png', 'image/webp')),
    size_bytes   INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX enquiry_attachments_enquiry_idx ON enquiry_attachments (enquiry_id);

CREATE TABLE enquiry_candidates (
    enquiry_id     UUID NOT NULL REFERENCES enquiries (id) ON DELETE CASCADE,
    rank           SMALLINT NOT NULL CHECK (rank BETWEEN 1 AND 10),
    part_id        INTEGER NOT NULL REFERENCES parts (id),
    score          NUMERIC(6, 5) NOT NULL CHECK (score >= 0 AND score <= 1),
    match_reasons  JSONB NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (enquiry_id, rank),
    UNIQUE (enquiry_id, part_id)
);

CREATE TABLE review_decisions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enquiry_id   UUID NOT NULL REFERENCES enquiries (id) ON DELETE CASCADE,
    reviewer     TEXT NOT NULL,
    decision     TEXT NOT NULL CHECK (decision IN ('approved', 'edited', 'rejected')),
    final_reply  TEXT,
    comment      TEXT,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (decision = 'rejected' OR final_reply IS NOT NULL)
);

CREATE INDEX review_decisions_enquiry_idx ON review_decisions (enquiry_id, decided_at DESC);

CREATE TABLE review_approved_parts (
    decision_id  UUID NOT NULL REFERENCES review_decisions (id) ON DELETE CASCADE,
    part_id      INTEGER NOT NULL REFERENCES parts (id),
    quantity     NUMERIC(10, 3) NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (decision_id, part_id)
);

-- ---------------------------------------------------------------------------
-- Append-only audit trail
-- ---------------------------------------------------------------------------

CREATE TABLE audit_log (
    id           BIGSERIAL PRIMARY KEY,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type   TEXT NOT NULL CHECK (actor_type IN ('system', 'ai', 'user')),
    actor_id     TEXT NOT NULL,
    action       TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    request_id   TEXT,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id, occurred_at DESC);

CREATE FUNCTION prevent_audit_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_audit_mutation();

COMMIT;
