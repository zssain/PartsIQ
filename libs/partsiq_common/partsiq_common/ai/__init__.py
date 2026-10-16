"""AI client subpackage: the single audited path to OpenAI.

No module here authorizes a fact. ``client.call_structured`` only turns untrusted
text/images into a validated structured-output JSON string under a budget reservation;
deterministic application code decides what to persist (CONSTRAINTS.md rules 5-6).
"""
