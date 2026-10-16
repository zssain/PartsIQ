# PartsIQ

AI-assisted spare-parts identification for equipment distributors. PartsIQ interprets incomplete
customer enquiries in English, Arabic or a mixture of both, identifies the exact machine
configuration, retrieves only parts that the catalogue records as compatible, recommends which
warehouse should supply them, and (from Milestone 3) drafts a reply that staff must approve.

This is an independent concept built entirely on synthetic data. All brands, models and part
numbers are fictional. It is not affiliated with or endorsed by any distributor or manufacturer.

## Core design principle

The language model reads and writes language; the database decides facts. Compatibility is
determined exclusively by `part_compatibility`. Ranking components only order parts that the
database has already declared compatible, and every recommendation carries its source reference.

## Architecture

| Service | Responsibility | Status |
|---|---|---|
| `gateway` | Authentication, rate limiting, request-ID propagation, routing | Complete |
| `search` | Machine identification, compatibility-constrained bilingual part search, fulfilment planning | Complete |
| `orchestrator` | LangGraph workflow: understand, clarify, search, verify, draft, await review | Milestone 3 |
| `worker` | Asynchronous nameplate OCR and catalogue ingestion via a Redis queue | Milestone 4 |

```
Client ──> gateway ──> search ──> PostgreSQL (pgvector, pg_trgm)
              │
              └──> orchestrator ──> search            (Milestone 3)
                        └──> Redis queue ──> worker   (Milestone 4)
```

## Operating assumptions

The system is designed to work across the range of real-world conditions rather than one assumed
workflow:

| Unknown | How PartsIQ handles it |
|---|---|
| Enquiry channel (WhatsApp, email, phone notes, walk-in) | Channel-agnostic API; the channel is recorded per enquiry |
| Language | Arabic, English and mixed text; Gulf colloquial terms (for example "كلارك", "سلف", "طرمبة") are catalogued as aliases |
| Missing serial or model | Identification returns `needs_serial`, `ambiguous_model` or `serial_mismatch` with a precise follow-up question instead of guessing |
| Customer quotes an old part number | Supersession chains are followed to the current part, and compatibility with the identified machine is reported |
| Local stock-out | Fulfilment recommends local, single transfer, split or back-order, using planned transfer lead times |
| Existing ERP or catalogue system | The catalogue is loaded from a portable dataset format; an adapter for a real source replaces the generator |

## The synthetic catalogue

`tools/catalog` generates a deterministic, internally consistent catalogue: 4 equipment families,
19 models, 29 configurations, 181 active parts, 17 superseded part numbers, 787 bilingual aliases
and stock across three regional warehouses. It deliberately includes the conditions that make
parts identification hard: look-alike parts that fit only one engine or mast variant, parts shared
across a size frame, superseded numbers, and stock-outs.

A validator checks consistency before loading (overlapping serial ranges, dangling references,
supersession cycles, active parts that fit no machine, missing transfer routes and more).

## Running locally

Prerequisites: Docker with Docker Compose v2.

```bash
cp .env.example .env
# Edit .env: set passwords and generate an API key:
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up --build -d
docker compose --profile tools run --rm catalog-tools seed
```

The schema in `db/migrations` is applied when the PostgreSQL volume is first created. If you ran
Milestone 1 previously, recreate the volume so migration 002 is applied: `docker compose down -v`
(this deletes local data), then repeat the steps above.

## Example requests

Set `KEY` to your API key. All requests go through the gateway on port 8080.

```bash
KEY=your-key
H=(-H "X-API-Key: $KEY" -H "Content-Type: application/json")

# 1. Identify the machine. Without a serial, a two-configuration model asks for one.
curl -s "${H[@]}" http://127.0.0.1:8080/api/v1/search/identify \
  -d '{"query": "VP-100 generator"}'

# 2. Serial numbers resolve the configuration. Serials can also appear inside the text.
curl -s "${H[@]}" http://127.0.0.1:8080/api/v1/search/identify \
  -d '{"query": "ابغى فلتر ديزل للمولد VP 100", "serial": "SN 340005"}'

# 3. Search compatible parts, using configuration.id from step 2.
curl -s "${H[@]}" http://127.0.0.1:8080/api/v1/search/parts \
  -d '{"configuration_id": 6, "query": "ابغى فلتر ديزل", "limit": 3}'

# 4. Look up any part number, including superseded ones; formatting is ignored.
curl -s "${H[@]}" http://127.0.0.1:8080/api/v1/search/parts/vp-of-2824

# 5. Plan fulfilment to a destination warehouse.
curl -s "${H[@]}" http://127.0.0.1:8080/api/v1/search/fulfilment \
  -d '{"part_number": "VP-OF-2824", "quantity": 6, "destination_warehouse": "RUH"}'
```

Configuration IDs depend on load order; always take them from the identify response. Part numbers
depend on the generator seed (default 42); list real ones with
`docker compose exec postgres psql -U partsiq -d partsiq -c "SELECT part_number, name_en FROM parts LIMIT 20"`.

Each part-search response includes `confidence.top_score` and `confidence.margin`. A small margin
(two near-equal candidates, such as a fuel filter and a fuel water separator) is the signal the
orchestrator will use to ask a verification question rather than present a single answer.

Interactive documentation for each service is available outside production at `/docs` (the
gateway on port 8080; the search service is internal and reachable from within the network).

## Semantic search (optional)

Lexical search handles Arabic normalisation, colloquial aliases, misspellings and phrase matching
without any model. To add multilingual vector search (BGE-M3, about 2 GB plus PyTorch):

```bash
# In .env
INSTALL_EMBEDDINGS=true
EMBEDDING_PROVIDER=sentence_transformers

docker compose up --build -d
docker compose --profile tools run --rm catalog-tools embed
```

The combined score is `(1 - SEMANTIC_WEIGHT) * lexical + SEMANTIC_WEIGHT * semantic`, with a
default semantic weight of 0.4.

## Tests

Each component has a self-contained test suite:

```bash
python -m venv .venv && source .venv/bin/activate
pip install ./libs/partsiq_common pytest==8.3.4

(cd services/gateway && pip install -r requirements.txt && pytest)
(cd services/search && pytest)
(cd tools/catalog && pytest)
```

Coverage includes Arabic normalisation, part-number extraction, lexical ranking (including
colloquial Arabic, misspellings and look-alike parts), machine identification (serial resolution,
ambiguity, mismatches), fulfilment planning, catalogue determinism and validator fault detection,
API key handling and route safety.

## Data model highlights

- `model_configurations` rejects overlapping serial ranges per model via an exclusion constraint.
- `part_compatibility` requires a `source_reference` on every row.
- `part_supersessions` rejects cycles through a trigger.
- `parts.part_number_key` is a generated canonical key so that formatting differences never
  prevent a match.
- `audit_log` is append-only at the database level.

## Roadmap

1. Infrastructure, schema, shared library, gateway. Complete.
2. Synthetic catalogue tooling and search service. Complete.
3. LangGraph orchestrator: enquiry extraction, clarifying questions, confidence thresholds,
   hallucination guard, human-review interrupt, audit logging.
4. Worker service for nameplate OCR and catalogue ingestion.
5. Chat interface and staff review dashboard.
6. Evaluation suite gated in CI, Langfuse tracing, Prometheus and Grafana.
7. Helm charts and Kubernetes deployment with worker autoscaling.
