CREATE TABLE load_runs (
    load_run_id VARCHAR2(64) PRIMARY KEY,
    source_file VARCHAR2(255) NOT NULL,
    started_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR2(30) NOT NULL
);

CREATE TABLE transactions (
    transaction_id VARCHAR2(32) PRIMARY KEY,
    account_id VARCHAR2(32) NOT NULL,
    txn_type VARCHAR2(10) NOT NULL,
    amount NUMBER(18, 2) NOT NULL,
    txn_date DATE NOT NULL,
    load_run_id VARCHAR2(64) REFERENCES load_runs(load_run_id),
    created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);

CREATE TABLE load_errors (
    error_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_run_id VARCHAR2(64) REFERENCES load_runs(load_run_id),
    line_number NUMBER NOT NULL,
    raw_line CLOB NOT NULL,
    reason VARCHAR2(1000) NOT NULL,
    created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
);

