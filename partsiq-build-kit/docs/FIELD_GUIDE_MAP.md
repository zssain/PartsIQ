# Collaboration practices

The original AI-Collaboration-Field-Guide.pdf remains in references for source review. The following practices apply its collaboration intent; these are not verbatim quotations from the source.

1. Explain product purpose in CONTEXT and PRD.
2. Establish architecture boundaries before feature edits.
3. Execute one sequenced prompt at a time.
4. Read existing legacy code before rewriting it.
5. Define typed contracts before UI assumptions.
6. Specify dependencies and exact installed versions.
7. Name source paths and creation ownership.
8. Make small independently reviewable commits.
9. Test behavior and negative boundaries.
10. Preserve actual failure evidence.
11. Maintain handover and session logs across sessions.
12. Keep security and cost constraints visible.
13. Separate model outputs from deterministic decisions.
14. Require human review before publication.
15. Verify artifacts and deployment rather than trusting generated claims.

ARCHITECTURE.md answers the eight architecture questions. Every implementation prompt includes context, contracts, logic, API flow, tests, commands, documentation, rollback and completion evidence.
