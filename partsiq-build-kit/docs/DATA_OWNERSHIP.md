# Data ownership and synchronization

## Source and serving responsibilities

| Data | Authoritative write owner | Read path | Consistency rule |
|---|---|---|---|
| Auth sessions | Supabase Auth | Verified JWT and auth service | Never trust browser role metadata |
| Enquiries and decisions | PostgreSQL application transactions | Scoped REST resources | Current revision and actor required |
| Catalogue version source | Snowflake loader | Version-addressed connector read | Immutable once accepted; hash and counts verified |
| Active catalogue | PostgreSQL activation transaction | Version-filtered relational mirror | Exactly one active pointer; no mixed versions |
| Stock snapshots | Source snapshot import | Validated serving stock rows | Timestamp and snapshot provenance retained |
| Private images/evidence/PDF | Supabase Storage | Authorized signed URLs | Bucket/object ID ownership required |
| AI allowance | PostgreSQL locked budget account | Backend budget wrapper | Reserve before call; no remote reporting dependency |
| Analytics | PostgreSQL outbox then Snowflake copy | Scoped live counts or admin warehouse reports | At-least-once transport, idempotent event key |
| Audit | PostgreSQL append-only application role | Authorized staff view | Business change and audit commit together |

## Catalogue publication protocol

1. Admin creates an import batch and uploads the file privately. Validation parses typed entities without evaluating formulas or macros.
2. Canonicalize each record by entity type, key and stable JSON encoding. Preserve numeric legacy IDs; new records receive IDs through a controlled allocator before the source snapshot is sealed. Compute each row hash and the whole snapshot hash over sorted records.
3. Validate duplicate keys, foreign references, serial-range overlap, nonblank provenance, supersession cycles, valid units and evidence file availability. Imported stock validates nonnegative quantities and timestamps independently.
4. A single publisher job obtains a bounded publication lease. Write the full immutable VERSION_ID to Snowflake. Before retry, read the existing version and require exact hash/count equality; conflicting content under the same ID is an error.
5. Read the version back through SnowflakeCatalogueRepository, validate duplicates before mapping rows, and compare observed counts/hash with the manifest. Standard table PK/FK declarations do not enforce this.
6. Stage a catalogue_syncs receipt. Begin a PostgreSQL transaction, acquire the catalogue advisory lock, and compare the caller's expected active version. Upsert relational rows in dependency order. Keep historical referenced IDs; hide removed rows using the active catalogue_records keyset. Recheck the enforced PostgreSQL constraints.
7. Retire the previous pointer and activate the new version in that same transaction. Commit the sync receipt and audit. If the transaction fails, the old version remains active and the remote version remains unactivated.
8. Pending enquiries detect a changed active version on their next processing/review action and require recomputation. Previously approved replies retain their immutable fact/evidence snapshot and are never rewritten as history.

Snowflake is not queried on every chat message or dashboard poll. The UI displays catalogue source, active version, last activation and stock observed time. Fixture mode uses the same validation contract and a different explicit source label. Never silently fall back from live Snowflake to fixtures after a failure.

## Snapshot payload contracts

The CATALOGUE.RECORDS payload uses the exact typed columns of the corresponding legacy PostgreSQL entity, excluding generated search_document and database timestamps where not business data. Supported entities: equipment_families, equipment_models, model_configurations, parts, part_aliases, part_compatibility, part_supersessions, warehouses, warehouse_transfer_routes. Key construction is deterministic: single numeric IDs use their decimal string; composite keys use compact JSON arrays of their primary-key values. A schema version is recorded in the import report. Unknown entity types/fields fail validation rather than being silently dropped.

Stock uses the dedicated Snowflake STOCK_SNAPSHOTS table. Preserve snapshot_id, observed_at and original units during serving import. One snapshot is activated transactionally only after all its rows validate. Approval checks age and availability but does not reserve stock; the final text clearly labels availability as a snapshot and delivery time as an estimate.

## Analytics transport

Business code appends an outbox event after redaction in the same PostgreSQL transaction. A single export job takes at most100 events, constructs bound MERGE statements keyed by event_id, and acknowledges only after Snowflake success. Duplicate remote IDs cause a diagnostic failure and repair; Snowflake primary-key metadata is not a uniqueness guarantee. A crash after remote commit replays the same event safely. Only allowlisted analytical columns are exported; no customer text, serial number, email, JWT, notes or signed URL enters Snowflake reporting.

Scoped live queue counts remain PostgreSQL queries. Snowflake reports are administrator-only aggregates and display sync lag. Reviewer dashboards never receive global unassigned counts. An expired trial freezes remote reporting and shows its last timestamp; it does not fabricate current metrics.

## Stock activation receipt

stock_snapshot_receipts records the source snapshot ID, observed timestamp, content hash, row count and active flag. Under the publication lock, upsert stock_levels and switch the single active stock receipt in one PostgreSQL transaction. All plan reads return that snapshot ID. Approval compares the current active stock snapshot and freshness against the draft; changed availability triggers a new plan. Do not use a null snapshot ID to hide missing provenance in live mode.
