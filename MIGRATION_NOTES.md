# Migration Notes

## Perl to Python Narrative

The legacy Perl loader reads pipe-delimited transaction records, validates fields with regular expressions, sums totals by transaction type, and flags large debit transactions. The Python migration keeps that behavior but separates parsing, validation, and loading into testable modules.

## Gotchas Captured

- Perl can silently coerce strings to numbers during comparisons. Python validation now parses amounts explicitly with `Decimal`.
- Perl hash auto-vivification makes accumulation concise but can hide misspelled keys. Python uses dataclasses and `defaultdict`.
- A naive split can accept extra delimiters. The Python parser checks the exact field count before constructing a record.
- Calendar parsing can be platform-sensitive in Perl if `Time::Piece->strptime` normalizes impossible dates instead of failing. The Perl baseline now round-trips parsed dates with `$tp->ymd`, while Python uses `date.fromisoformat`.
- Vendor files can arrive with CRLF line endings over SFTP. The Perl baseline strips `\r?\n` instead of relying on `chomp`, and the Python parser has fixture coverage for CRLF input.
- A code-review pass on the Python side also caught a stray `-?` in the amount regex that would have silently accepted negative amounts — contradicting the Perl baseline's explicit design intent that amounts are positive-only since `txn_type` already carries the direction. Fixed in both `validate.py` and `config/field_mapping.yaml`, with a regression test added.
- The Python CLI (`loader.py main()`) did not originally propagate a failure exit code when records were rejected, unlike the Perl baseline's `exit 1`. An orchestrator watching exit codes would have seen a 100%-rejected run as a success. Fixed with a regression test covering both the failure and success paths.
- Oracle inserts were originally issued one `execute()` call per record. Switched to batched `executemany()` (default batch size 500) — row-by-row execution is a common cause of a load that used to take minutes silently regressing to an hour as data volume grows.

## Deliberate Schema Changes (Python target format vs. Perl source format)

These are intentional, not migration bugs — documented here so a reconciliation reviewer doesn't mistake them for equivalence failures:

- **Added a `transaction_id` field**, making the target format 5 fields (`transaction_id|account_id|txn_type|amount|txn_date`) instead of the Perl baseline's original 4 (`account_id|txn_type|amount|date`). The Perl source format has no natural unique key per record; `transaction_id` was introduced specifically to serve as the `MERGE` key in `oracle_client.py`, which is what makes reruns of `load_to_oracle` idempotent. In a real migration, this field would need to come from the upstream source system (or be generated deterministically at ingestion) rather than assumed present — that's an open question for the real vendor file format, not yet resolved here.
- **Tightened `account_id` from Perl's loose `^[A-Za-z0-9_]+$` to a strict `^ACCT-\d{6}$`.** Note this is stricter than even the Perl script's own documented example (`ACC1001`, no hyphen, 4 digits) — the Python format was chosen for the test fixtures and is not yet verified against a real source file's actual account ID format. This needs confirming against real data before treating it as final; it's currently an assumption, not a verified requirement.

## Validation Approach

Correctness is checked at four levels:

- Unit tests compare parser and validator behavior for valid, malformed, and edge-case records.
- Loader tests verify totals, large debit detection, config-driven validation (via `field_mapping.yaml`), and CLI exit-code behavior.
- Oracle-client tests verify the merge contract is idempotent, batched via `executemany`, and mock-friendly — plus row-level checksum reconciliation (`reconcile_row_level`), which catches same-count/same-sum-but-wrong-records cases that count/sum comparison alone would miss.
- DAG tests (`tests/test_dag.py`, skipped unless Airflow is installed — see the `dag-validation` CI job) confirm the DAG imports without errors and that the three tasks are actually wired together in dependency order, not just present.

## Cutover Approach

In a real migration, both loaders would run in parallel for a controlled window. Source counts, rejected-record counts, totals by transaction type, and target checksums would be compared before switching scheduling from the Perl job to the Python Airflow DAG.
