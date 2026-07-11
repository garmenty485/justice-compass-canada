"""Call from Medallion / deploy notebooks to log runs to Lakebase."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def log_from_notebook(
    dbutils: Any,
    layer: str,
    status: str,
    *,
    row_count: int | None = None,
    error_message: str | None = None,
) -> None:
    try:
        nb_path = (
            dbutils.notebook.entry_point.getDbutils()
            .notebook()
            .getContext()
            .notebookPath()
            .get()
        )
        repo_rel = nb_path.split("/databricks/notebooks/")[0]
        repo_root = repo_rel if repo_rel.startswith("/Workspace") else f"/Workspace{repo_rel}"
        lakebase_dir = Path(repo_root) / "databricks" / "lakebase"
        import sys

        if str(lakebase_dir) not in sys.path:
            sys.path.insert(0, str(lakebase_dir))
        from pipeline_log import log_pipeline_run

        log_pipeline_run(
            layer,
            status,
            row_count=row_count,
            error_message=error_message,
            dbutils=dbutils,
        )
    except Exception as exc:
        print(f"Lakebase log skipped: {exc}")
