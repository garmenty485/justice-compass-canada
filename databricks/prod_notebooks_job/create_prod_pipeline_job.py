# Databricks notebook source
# MAGIC %md
# MAGIC # Create Prod Pipeline Job (01 → 02 → 03 → 05 → 09)
# MAGIC
# MAGIC Creates or updates **`justice-compass-prod-pipeline`** (no schedule — GHA triggers run-now).
# MAGIC
# MAGIC **After create**: copy `job_id` → GitHub Secret `DATABRICKS_PROD_JOB_ID`.

# COMMAND ----------

RUN_NOW = True

# COMMAND ----------

from pathlib import Path
import sys

PROD_MARKER = "/databricks/prod_notebooks_job/"
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
if PROD_MARKER not in _nb:
    raise RuntimeError(f"Run from prod_notebooks_job/: {_nb}")
_rel = _nb.split(PROD_MARKER)[0]
_root = _rel if _rel.startswith("/Workspace") else f"/Workspace{_rel}"
sys.path.insert(0, str(Path(_root) / "databricks" / "prod_notebooks_job"))

from prod_pipeline_job import create_or_update_job, print_job_result, run_job_now  # noqa: E402

result = create_or_update_job(dbutils)
print_job_result(result)
print(f"\n→ Set GitHub Secret DATABRICKS_PROD_JOB_ID={result['job_id']}")

# COMMAND ----------

if RUN_NOW:
    run = run_job_now(dbutils, result["job_id"])
    print(f"Triggered run_id={run.get('run_id')}")
else:
    print("Set RUN_NOW = True to test immediately, or use GHA workflow_dispatch.")
