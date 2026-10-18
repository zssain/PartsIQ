# Start or resume implementation

You are implementing the PartsIQ single-workflow Snowflake edition from this repository. Read AGENTS.md, docs/CONTEXT.md, docs/HANDOVER.md and prompts/README.md. Identify the first uncompleted prompt in spec/build-order.json. Inspect its prerequisites and current source before editing.

Complete that prompt in full: typed contracts, domain behavior, REST adapters, UI where specified, permissions, failure handling, tests, documentation and commit. Preserve all 69 features and the fixed compatibility/human approval rules. No agent framework is part of the runtime. Use Snowflake only through the catalogue/reporting adapters and Supabase for operational state/auth/files. Respect the zero-paid-budget gate.

Run the prompt's named checks and record actual outcomes. Do not claim a service was deployed or a live provider was tested without execution evidence. If one external dependency blocks a check, finish independent local implementation and identify the exact missing account/configuration. Update handover and feature trace before returning. Never shorten implementation to a mock UI when the prompt calls for working backend behavior.
