-- Search and fulfilment support.

BEGIN;

-- Canonical part-number key so that "vp of 1042", "VP-OF-1042" and "VPOF1042" all match.
-- Must remain consistent with partsiq_common.text.part_number_key.
ALTER TABLE parts
    ADD COLUMN part_number_key TEXT GENERATED ALWAYS AS (
        upper(regexp_replace(part_number, '[^A-Za-z0-9]', '', 'g'))
    ) STORED;

CREATE INDEX parts_part_number_key_idx ON parts (part_number_key);

-- Planned transfer lead times between warehouses, used to recommend where to fulfil from.
CREATE TABLE warehouse_transfer_routes (
    from_warehouse_id  SMALLINT NOT NULL REFERENCES warehouses (id) ON DELETE CASCADE,
    to_warehouse_id    SMALLINT NOT NULL REFERENCES warehouses (id) ON DELETE CASCADE,
    transfer_days      SMALLINT NOT NULL CHECK (transfer_days BETWEEN 1 AND 60),
    PRIMARY KEY (from_warehouse_id, to_warehouse_id),
    CHECK (from_warehouse_id <> to_warehouse_id)
);

COMMIT;
