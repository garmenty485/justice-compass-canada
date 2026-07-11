"""Unit tests for prod pipeline job settings (no Databricks runtime)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "databricks" / "prod_notebooks_job"))

from prod_pipeline_job import (  # noqa: E402
    DEFAULT_SYNCED_TABLE_UC_NAME,
    JOB_NAME,
    build_job_settings,
    notebook_paths,
)


def test_prod_notebook_paths():
    repo = "/Workspace/Repos/user@github.com/justice-compass"
    paths = notebook_paths(repo)
    assert paths["bronze_ingest"].endswith(
        "/databricks/prod_notebooks_job/01_bronze_ingest"
    )
    assert paths["sync_cases"].endswith(
        "/databricks/prod_notebooks_job/09_sync_cases_prod"
    )


def test_prod_job_settings_task_chain():
    repo = "/Workspace/Repos/user@github.com/justice-compass"
    settings = build_job_settings(repo)
    assert settings["name"] == JOB_NAME
    assert settings["max_concurrent_runs"] == 1
    assert "schedule" not in settings
    tasks = {t["task_key"]: t for t in settings["tasks"]}
    assert tasks["silver_transform"]["depends_on"] == [{"task_key": "bronze_ingest"}]
    assert tasks["deploy_serving"]["depends_on"] == [{"task_key": "gold_embed"}]
    assert tasks["sync_cases"]["depends_on"] == [{"task_key": "deploy_serving"}]
    sync_nb = tasks["sync_cases"]["notebook_task"]
    assert sync_nb["base_parameters"]["SYNCED_TABLE_UC_NAME"] == DEFAULT_SYNCED_TABLE_UC_NAME
    assert len(tasks) == 5
