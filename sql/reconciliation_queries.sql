-- Row count by load run.
SELECT load_run_id, COUNT(*) AS target_count
FROM transactions
GROUP BY load_run_id;

-- Amount total by load run.
SELECT load_run_id, SUM(amount) AS target_amount_total
FROM transactions
GROUP BY load_run_id;

-- Deterministic checksum input for external comparison.
-- Amount and date are explicitly formatted with TO_CHAR rather than
-- relying on implicit to-string conversion, which is governed by session
-- NLS settings (NLS_NUMERIC_CHARACTERS, NLS_DATE_FORMAT) and can silently
-- drift from how the Python side formats the same value, producing false
-- reconciliation mismatches. Must be kept in sync with
-- pipeline.oracle_client.CHECKSUM_QUERY_SQL and pipeline.oracle_client._checksum().
SELECT transaction_id || '|' || account_id || '|' || txn_type || '|' ||
       TO_CHAR(amount, 'FM999999999990.00') || '|' ||
       TO_CHAR(txn_date, 'YYYY-MM-DD') AS checksum_input
FROM transactions
WHERE load_run_id = :load_run_id
ORDER BY transaction_id;

