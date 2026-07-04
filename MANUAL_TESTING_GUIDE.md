# Manual Testing Guide — legacy-pipeline-migrator (Ubuntu / WSL)

Run these in order. Each stage builds on the last — don't skip ahead if
something fails, fix it there first.

---

## 0. Prerequisites (one-time check)

```bash
python3 --version        # expect 3.10+
docker --version         # expect Docker Desktop's engine, via WSL integration
docker compose version   # v2 syntax (no hyphen) — this project uses it throughout
git --version
```

If `docker` isn't found: open Docker Desktop on Windows → Settings → Resources →
WSL Integration → enable for your Ubuntu distro → Apply & Restart.

---

## 1. Get the code and set up the venv

```bash
cd ~/Projects/Python/legacy-pipeline-migrator   # or wherever you cloned it

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

That's the only install command you need — `paramiko`, `oracledb`, and `PyYAML`
are all listed in `pyproject.toml`'s core `dependencies`, so `.[dev]` (which
adds `pytest`/`ruff` on top) pulls in everything in one shot.

**Verify:**
```bash
pip show paramiko oracledb PyYAML pytest ruff
```
All five should show as installed — if any are missing, `pip install -e ".[dev]"`
didn't complete; check its output for errors before continuing.

---

## 2. Lint

```bash
ruff check .
```
Expected: `All checks passed!`

---

## 3. Fast unit test suite (no Docker, no Oracle, no Airflow needed)

```bash
pytest -v
```
Expected: **32 passed, 1 skipped, 4 deselected**
- The 1 skip is `tests/test_dag.py` — it needs Airflow installed (Section 6).
- The 4 deselected are `tests/integration/` — they need live Oracle (Section 5).

If you see failures here, stop and fix them before moving on — nothing past
this point depends on Docker/Airflow, so a failure here is a real code issue,
not an environment issue.

---

## 4. Try the CLI directly against a fixture

```bash
python -m pipeline.loader tests/fixtures/valid_transactions.txt
echo "exit code: $?"
```
Expected: prints accepted/rejected counts and totals, exit code `0`.

```bash
python -m pipeline.loader tests/fixtures/malformed_transactions.txt
echo "exit code: $?"
```
Expected: `rejected=5`, exit code **`1`** — this is the CLI exit-code fix from
the review; if this prints `0`, something regressed.

---

## 5. Docker: Oracle + SFTP + real integration tests

### 5a. Configure environment
```bash
cp .env.example .env
```
Defaults in `.env.example` work as-is for local testing — no need to edit
anything unless you want different credentials.

### 5b. Bring up the containers
```bash
docker compose up -d oracle sftp
```

### 5c. Watch Oracle come up healthy
First run pulls the image and can take a couple of minutes; subsequent runs
are much faster (~30-60s to healthy).
```bash
docker compose ps
```
Wait until the `oracle` row shows `(healthy)` in the STATUS column. To watch
it live instead of polling manually:
```bash
watch docker compose ps
```
(Ctrl+C once it flips to healthy.)

**If it never goes healthy** — check logs:
```bash
docker compose logs oracle --tail 50
```
Common cause on WSL: Oracle needs a fair amount of RAM. If WSL is starved,
increase the limit in `%UserProfile%\.wslconfig` on the Windows side:
```ini
[wsl2]
memory=6GB
```
Then `wsl --shutdown` from PowerShell and reopen your Ubuntu terminal.

**To try fresh DB/sftp service: wipe the volume and start clean **
```bash
docker compose down -v      # -v removes the named volume along with the containers.
docker volume ls | grep oracle # Confirm it's actually gone: Should return nothing.
docker compose up -d oracle sftp # start fresh
docker compose logs -f oracle  # check logs of oracle container
```

### 5d. Export the connection variables and run integration tests
```bash
source .env
export ORACLE_USER ORACLE_PASSWORD
export ORACLE_DSN="localhost:1521/${ORACLE_PDB:-FREEPDB1}"

pytest -m integration -v
```
Expected: **4 passed** (not skipped this time, since Oracle is actually reachable):
- `test_upsert_transactions_against_real_oracle`
- `test_upsert_is_idempotent_on_rerun` — the most important one; proves rerunning the same load doesn't create duplicate rows
- `test_reconcile_row_level_matches_after_real_load`
- `test_reconcile_row_level_detects_real_drift`

**If you get a connection error** (`ORA-12541` / `no listener`), Oracle probably
isn't fully healthy yet despite what `docker compose ps` showed — wait another
30s and retry.

### 5e. Poke around manually (optional but satisfying)
```bash
docker exec -it legacy-pipeline-oracle sqlplus migrator/dev_password@//localhost:1521/FREEPDB1
```
```sql
SELECT COUNT(*) FROM transactions;
SELECT * FROM load_runs ORDER BY started_at DESC FETCH FIRST 5 ROWS ONLY;
EXIT;
```

### 5f. Tear down when done
```bash
docker compose down
```
Add `-v` if you also want to wipe the Oracle data volume and start fresh next
time: `docker compose down -v`.

**Or skip 5a-5f entirely and use the one-shot script:**
```bash
./scripts/run_integration_tests.sh          # up, test, down automatically
./scripts/run_integration_tests.sh --keep   # leaves containers running after
```

---

## 6. Validate the Airflow DAG (optional, separate from core dev)

Airflow is intentionally not part of `.[dev]` — it's heavy and has its own
pinned constraints file. Install it only when you want to check the DAG:

```bash
AIRFLOW_VERSION=2.9.3
PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
pip install "apache-airflow==${AIRFLOW_VERSION}" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

pytest tests/test_dag.py -v
```
Expected: **3 passed** — DAG imports with zero errors, correct task IDs, correct
dependency chain, correct retry counts per task (0 for `validate_file`, 3 for
the other two).

Run the full suite again afterward and you should now see **35 passed** (the
previous skip becomes a pass since Airflow is now installed).

---

## 7. Build and run the app as a container

```bash
docker compose build app
docker compose run --rm app tests/fixtures/valid_transactions.txt
```
Expected: same output as Section 4, but running inside the container — proves
the packaging (`Dockerfile`) actually works standalone, independent of your
local venv.

```bash
docker compose run --rm app --help
```
Should print argparse usage (confirms the default `CMD` in the `Dockerfile`).

---

## 8. Seeing the containers (K9s won't show these — see below)

```bash
docker compose ps       # what's running, health status
docker compose logs -f  # tail all container logs together
```

If you want a K9s-like interactive TUI for plain Docker (not Kubernetes):
```bash
# via go install, if you have Go:
go install github.com/jesseduffield/lazydocker@latest
# or via the install script:
curl https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/install_update_linux.sh | bash
lazydocker
```
Reminder: these are plain Docker containers, not Kubernetes pods — K9s
specifically won't see them regardless of what's running, since it only talks
to a Kubernetes API server.

---

## 9. Full clean-up

```bash
docker compose down -v   # stop containers, remove volumes (fresh Oracle next time)
deactivate                # exit the Python venv
```

---

## Quick Reference: Expected Pass Counts at Each Stage

| Command | Expected result |
|---|---|
| `ruff check .` | All checks passed! |
| `pytest -v` (no Airflow, no Docker) | 32 passed, 1 skipped, 4 deselected |
| `pytest -v` (Airflow installed, no Docker) | 35 passed, 4 deselected |
| `pytest -m integration -v` (Oracle running) | 4 passed |
| `pytest -v` (Airflow installed AND Oracle running) | 39 passed |

If your numbers ever come in lower than expected, something regressed —
worth tracking down before pushing, rather than assuming it's environmental.
