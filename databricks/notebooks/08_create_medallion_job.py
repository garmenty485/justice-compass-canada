# Databricks notebook source
# MAGIC %md
# MAGIC # 08 — Create Medallion Job (01 → 02 → 03)
# MAGIC
# MAGIC Creates or updates **`justice-compass-medallion`** via Jobs API (serverless notebook tasks).
# MAGIC
# MAGIC **Prerequisite**: Git folder **Pull** latest; Lakebase secrets optional (each task logs `pipeline_runs` if configured).
# MAGIC
# MAGIC **After this notebook**: Workflows → Jobs → **Run now** on `justice-compass-medallion`, or set `RUN_NOW = True` below.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Config

# COMMAND ----------

RUN_NOW = False  # set True to trigger a run immediately after create/update

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create or update Job

# COMMAND ----------

from pathlib import Path
import sys

_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_rel = _nb.split("/databricks/notebooks/")[0]
_root = _rel if _rel.startswith("/Workspace") else f"/Workspace{_rel}"
sys.path.insert(0, str(Path(_root) / "databricks" / "jobs"))

from medallion_job import create_or_update_job, print_job_result, run_job_now  # noqa: E402

result = create_or_update_job(dbutils)
print_job_result(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optional: Run now

# COMMAND ----------

if RUN_NOW:
    run = run_job_now(dbutils, result["job_id"])
    run_id = run.get("run_id")
    print(f"Triggered run_id={run_id}")
    print("Track: Workflows → Jobs → justice-compass-medallion → Runs")
else:
    print("Set RUN_NOW = True to trigger immediately, or use Jobs UI → Run now.")
