# Typed contracts

The complete executable model definitions are in spec/contracts.py and spec/api_models.py. Their JSON schemas are in spec/contracts.schema.json and the complete HTTP schema is spec/openapi.json. Copy them into partsiq.core in foundation 01. Keep nested fields, limits, enums and nullability unchanged unless a documented correction is required.

The API inventory and access rules are in REST_API.md. Foundation prompts define domain function signatures; feature prompts define facade signatures and exact wire request/response models. Decimal values are serialized as strings. Source record payloads have schema validation keyed by entity type and may never be accepted as arbitrary JSON for publication.
