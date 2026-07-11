"""Unit tests for medallion job settings (no Databricks runtime)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "databricks" / "jobs"))

from medallion_job import JOB_NAME, build_job_settings, notebook_paths  # noqa: E402


def test_notebook_paths():
    repo = "/Workspace/Repos/user@github.com/justice-compass"
    paths = notebook_paths(repo)
    assert paths["bronze_ingest"].endswith("/databricks/notebooks/01_bronze_ingest")
    assert paths["gold_embed"].endswith("/databricks/notebooks/03_gold_embed")


def test_build_job_settings_tasks_chain():
    repo = "/Workspace/Repos/user@github.com/justice-compass"
    settings = build_job_settings(repo)
    assert settings["name"] == JOB_NAME
    tasks = {t["task_key"]: t for t in settings["tasks"]}
    assert tasks["silver_transform"]["depends_on"] == [{"task_key": "bronze_ingest"}]
    assert tasks["gold_embed"]["depends_on"] == [{"task_key": "silver_transform"}]
    assert "01_bronze_ingest" in tasks["bronze_ingest"]["notebook_task"]["notebook_path"]
