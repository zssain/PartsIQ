# Snowflake implementation guide

## What the integration demonstrates

PartsIQ uses Snowflake for immutable catalogue ingestion, inventory snapshots and analytical reporting. This is a data-platform integration, not a replacement for Supabase authentication or a place to run an autonomous SQL agent. Interactive REST reads use the validated serving copy. The demo should visibly show source version, hash, activation time and reporting sync time so the integration is concrete.

## Exact client and API choices

Pin snowflake-connector-python4.8.0, released30 September 2026. Its installation receipt is in spec/dependency-receipts.json. Version5.0.0 was released15 October and does not meet this kit's14-day stability window. Current online docs may show5.x renamed connection parameters; the implementation must follow the pinned4.8 signature and smoke-test it. Use connect with account, user, private_key_file, private_key_file_pwd, role, warehouse, database, schema, paramstyle='qmark', login_timeout=10 and network_timeout=30. Set STATEMENT_TIMEOUT_IN_SECONDS=20 and a request-UUID QUERY_TAG through session_parameters.

Use Connection.cursor, Cursor.execute with bound values, Cursor.fetchall or fetchmany for bounded reads, Cursor.sfqid for a query receipt, and close both resources in finally. Use explicit BEGIN/COMMIT/ROLLBACK for a logical remote write; DDL is setup-only and must not be mixed into transactional import publication. Do not share one live connection among unrelated async tasks. The connector is blocking: call it in asyncio.to_thread in the worker with at most2concurrent tasks. Cancellation of the awaiting coroutine is not proof that a remote statement stopped; retain query ID and classify uncertain completion for reconciliation.

Example read query is fixed SQL: SELECT ENTITY_TYPE, ENTITY_KEY, PAYLOAD, ROW_SHA256 FROM PARTSIQ_DEV.CATALOGUE.RECORDS WHERE VERSION_ID=? ORDER BY ENTITY_TYPE, ENTITY_KEY. Bind(str(version_id), ). Database/schema identifiers cannot be value placeholders; choose them from the fixed validated environment allowlist. JSON payloads are parsed and checked against entity schemas. No user field becomes an identifier or SQL fragment.

## Schema and roles

Apply infra/snowflake/001_schema.sql, 002_roles.sql and003_validation_queries.sql after copying them from spec. Development uses PARTSIQ_DEV and production uses PARTSIQ_PROD through the setup tool's allowlisted substitution. CATALOGUE.VERSIONS stores the version manifest; RECORDS stores typed entity records; STOCK_SNAPSHOTS stores inventory observations. REPORTING.EVENTS stores redacted events and DAILY_METRICS aggregates them. Snowflake standard tables have no application-defined indexes; do not promise PostgreSQL indexes/RLS on these tables. The initial small catalogue does not require clustering or search optimization services.

PARTSIQ_READER can read catalogue tables. PARTSIQ_LOADER has reader access plus controlled writes. PARTSIQ_REPORTER can write/read reporting events and read the report view. Each service identity has only its required role and warehouse usage. No application uses ACCOUNTADMIN, SECURITYADMIN or table-owner credentials. Loader permissions technically allow mutation, but application code rejects changing a sealed version; administrative bypass capability must be documented rather than called tamper-proof.

## Validation and publication

Run duplicate-key diagnostics before mapping rows into dictionaries. Validate referential integrity, serial ranges, supersession graph, evidence and stock in Python and again through PostgreSQL constraints on activation. Never use RELY to optimize declared constraints unless the validation pipeline actually guarantees them. The full activation protocol is in DATA_OWNERSHIP.md. An unactivated remote version has no effect on customer search. Failed activation returns an actionable import report with row/field/code and preserves the previous active data.

## Reporting and replay

Select at most100 pending analytics events from PostgreSQL. Redact to the defined reporting columns, then MERGE by EVENT_ID under a single exporter lease. Same EVENT_ID with conflicting payload is an integrity error, not a silent update. On retry, identical existing data is success. Acknowledge PostgreSQL only after Snowflake succeeds. Track query ID, row count, last success time and pending backlog. Do not export raw text or identity data. Dashboard labels distinguish live operational counts from delayed Snowflake aggregates.

## Cost and availability

The standard trial lasts30days or until free usage balance is exhausted, whichever happens first. This is not a permanent free tier. Confirm actual balance/expiry before creating or resuming a warehouse. Use one X-Small warehouse with AUTO_SUSPEND=60, AUTO_RESUME=true, INITIALLY_SUSPENDED=true and bounded statement timeouts only when allowance permits. Frequent wakeups still incur minimum resume billing; batch imports/reports and do not run warehouse queries during UI polling. Disable Cortex, Snowpipe, automatic clustering and other unneeded billable features.

A resource monitor is a guardrail, not a hard no-charge guarantee: warehouse suspension may lag and some serverless/cloud-service usage is outside its coverage. The application additionally checks the configured expiry and refuses scheduled remote work after it. Do not automatically attach a payment method or upgrade a trial. After expiry, the operator can select fixture mode explicitly or demonstrate a previously validated labelled snapshot under freshness policy; live Snowflake verification remains unavailable.

## Verification checklist

Verify key-pair login with the correct account/role, one bounded SELECT, round-trip of the synthetic catalogue, duplicate-key rejection, serial-overlap rejection, checksum mismatch, remote success/local failure, retry without duplicate reporting, expired allowance, and UI freshness labels. Save query IDs and counts without secrets. Offline fixtures verify domain behavior but are not a substitute for these live checks.

## Official references checked16 October 2026

- https://docs.snowflake.com/en/release-notes/clients-drivers/monthly-releases
- https://pypi.org/pypi/snowflake-connector-python/4.8.0/json
- https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api
- https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-upgrade
- https://docs.snowflake.com/en/sql-reference/constraints
- https://docs.snowflake.com/en/user-guide/admin-trial-account
- https://docs.snowflake.com/en/user-guide/resource-monitors
- https://docs.snowflake.com/en/user-guide/warehouses-considerations
