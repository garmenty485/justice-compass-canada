"""
Create or update the justice-compass-medallion Job (01 → 02 → 03).

Uses Jobs API 2.1 with serverless notebook tasks. Notebook paths are resolved
from the Git folder where this code runs (same pattern as 01/07).
"""

from __future__ import annotations

import json
from typing import Any

import requests

JOB_NAME = "justice-compass-medallion"

NOTEBOOKS = (
    ("bronze_ingest", "01_bronze_ingest"),
    ("silver_transform", "02_silver_transform"),
    ("gold_embed", "03_gold_embed"),
)


def get_api_context(dbutils: Any) -> tuple[str, str]:
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    return ctx.apiUrl().get(), ctx.apiToken().get()


def resolve_repo_root(dbutils: Any) -> str:
    nb_path = (
        dbutils.notebook.entry_point.getDbutils()
        .notebook()
        .getContext()
        .notebookPath()
        .get()
    )
    marker = "/databricks/notebooks/"
    if marker not in nb_path:
        raise RuntimeError(
            f"Unexpected notebook path: {nb_path}. "
            "Run from justice-compass/databricks/notebooks/ in a Git folder."
        )
    repo_rel = nb_path.split(marker)[0]
    return repo_rel if repo_rel.startswith("/Workspace") else f"/Workspace{repo_rel}"


def notebook_paths(repo_root: str) -> dict[str, str]:
    base = f"{repo_root}/databricks/notebooks"
    return {task_key: f"{base}/{stem}" for task_key, stem in NOTEBOOKS}


def build_job_settings(repo_root: str, *, name: str = JOB_NAME) -> dict[str, Any]:
    paths = notebook_paths(repo_root)
    bronze, silver, gold = (
        paths["bronze_ingest"],
        paths["silver_transform"],
        paths["gold_embed"],
    )
    return {
        "name": name,
        "description": "Bronze → Silver → Gold Medallion pipeline for Justice Compass",
        "max_concurrent_runs": 1,
        "tasks": [
            {
                "task_key": "bronze_ingest",
                "notebook_task": {"notebook_path": bronze, "source": "WORKSPACE"},
            },
            {
                "task_key": "silver_transform",
                "depends_on": [{"task_key": "bronze_ingest"}],
                "notebook_task": {"notebook_path": silver, "source": "WORKSPACE"},
            },
            {
                "task_key": "gold_embed",
                "depends_on": [{"task_key": "silver_transform"}],
                "notebook_task": {"notebook_path": gold, "source": "WORKSPACE"},
            },
        ],
    }


def _headers(api_token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
    }


def find_job_id(api_root: str, api_token: str, name: str = JOB_NAME) -> int | None:
    url = f"{api_root}/api/2.1/jobs/list"
    offset = 0
    while True:
        res = requests.get(
            url,
            headers=_headers(api_token),
            params={"limit": 100, "offset": offset, "name": name},
            timeout=60,
        )
        res.raise_for_status()
        body = res.json()
        for job in body.get("jobs", []):
            if job.get("settings", {}).get("name") == name:
                return int(job["job_id"])
        if not body.get("has_more", False):
            return None
        offset += 100


def create_or_update_job(
    dbutils: Any,
    *,
    name: str = JOB_NAME,
) -> dict[str, Any]:
    api_root, api_token = get_api_context(dbutils)
    repo_root = resolve_repo_root(dbutils)
    settings = build_job_settings(repo_root, name=name)
    existing_id = find_job_id(api_root, api_token, name=name)

    if existing_id is not None:
        url = f"{api_root}/api/2.1/jobs/reset"
        payload = {"job_id": existing_id, "new_settings": settings}
        res = requests.post(url, headers=_headers(api_token), json=payload, timeout=60)
        action = "updated"
        job_id = existing_id
    else:
        url = f"{api_root}/api/2.1/jobs/create"
        res = requests.post(url, headers=_headers(api_token), json=settings, timeout=60)
        action = "created"
        job_id = None

    if not res.ok:
        raise RuntimeError(
            f"Jobs API {action} failed ({res.status_code}): {res.text[:800]}"
        )

    body = res.json()
    if job_id is None:
        job_id = int(body["job_id"])

    return {
        "action": action,
        "job_id": job_id,
        "job_name": name,
        "notebook_paths": notebook_paths(repo_root),
        "settings": settings,
    }


def run_job_now(dbutils: Any, job_id: int) -> dict[str, Any]:
    api_root, api_token = get_api_context(dbutils)
    url = f"{api_root}/api/2.1/jobs/run-now"
    res = requests.post(
        url,
        headers=_headers(api_token),
        json={"job_id": job_id},
        timeout=60,
    )
    if not res.ok:
        raise RuntimeError(f"run-now failed ({res.status_code}): {res.text[:800]}")
    return res.json()


def print_job_result(result: dict[str, Any]) -> None:
    print(f"Job {result['action']}: {result['job_name']} (id={result['job_id']})")
    print("Notebook paths:")
    for key, path in result["notebook_paths"].items():
        print(f"  {key}: {path}")
