from __future__ import annotations

import pytest

# Airflow is a heavy, optional dependency — not part of the core dev
# install (see pyproject.toml). This test only runs where it's present,
# e.g. the dedicated dag-validation job in CI. Locally, without Airflow
# installed, it's skipped rather than failing the whole suite.
pytest.importorskip("airflow")


def test_dag_imports_without_errors() -> None:
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder="dags", include_examples=False)

    assert dag_bag.import_errors == {}
    assert "transaction_pipeline" in dag_bag.dags


def test_dag_has_expected_tasks_in_order() -> None:
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder="dags", include_examples=False)
    dag = dag_bag.dags["transaction_pipeline"]

    task_ids = {task.task_id for task in dag.tasks}
    assert task_ids == {"wait_for_marker", "validate_file", "load_to_oracle"}

    validate_task = dag.get_task("validate_file")
    load_task = dag.get_task("load_to_oracle")
    marker_task = dag.get_task("wait_for_marker")

    # Confirms the dependency chain actually wires the three real pipeline
    # steps together, not just three disconnected tasks.
    assert validate_task.upstream_task_ids == {"wait_for_marker"}
    assert load_task.upstream_task_ids == {"validate_file"}
    assert marker_task.upstream_task_ids == set()


def test_validate_file_task_has_no_retries() -> None:
    # Deterministic data-quality failures shouldn't be retried — see the
    # comment in dags/transaction_pipeline_dag.py.
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder="dags", include_examples=False)
    dag = dag_bag.dags["transaction_pipeline"]

    assert dag.get_task("validate_file").retries == 0
    assert dag.get_task("wait_for_marker").retries == 3
    assert dag.get_task("load_to_oracle").retries == 3
