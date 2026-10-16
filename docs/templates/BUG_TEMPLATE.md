# BUG-001 - Duplicate approval example
## Reproduction
Submit the same approval twice with one idempotency key against a disposable demo enquiry.
## Expected
One review decision and one recommendation message.
## Actual
Record observed rows and request IDs during reproduction; this template is an example,not a reported live defect.
## Hypothesis
Missing transaction lock or unique publication constraint.
## Investigation
Inspect approval transaction,idempotency lookup and messages_one_publication_idx.
## Fix
Use current-revision transaction and uniqueness; do not suppress all database errors.
## Verification
Run concurrent approval test;record actual output and commit when this example is used for a real bug.
