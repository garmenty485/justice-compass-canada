# Databricks notebook source
# MAGIC %md
# MAGIC # Prod 09 — Sync cases metadata + trigger Synced Table
# MAGIC
# MAGIC **Scheduled prod path only** — refresh `cases_metadata` (INSERT OVERWRITE, preserves Delta table ID)
# MAGIC and trigger the Synced Table pipeline.
# MAGIC One-time UI setup: see `SETUP.md` in this folder.

# COMMAND ----------

dbutils.widgets.text("SYNCED_TABLE_UC_NAME", "workspace.default.cases_meta_synced", "Synced table UC name (three-part)")

UC_CATALOG = "workspace"
UC_SCHEMA = "default"
BRONZE_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.bronze_cases"
CASES_METADATA_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.cases_metadata"

# COMMAND ----------

import sys
from pathlib import Path

PROD_MARKER = "/databricks/prod_notebooks_job/"
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_rel = _nb.split(PROD_MARKER)[0]
_root = _rel if _rel.startswith("/Workspace") else f"/Workspace{_rel}"
_lakebase_dir = Path(_root) / "databricks" / "lakebase"
sys.path.insert(0, str(_lakebase_dir))

from cases_metadata import refresh_cases_metadata  # noqa: E402
from secret_utils import resolve_synced_table_uc_name  # noqa: E402

_widget_synced = dbutils.widgets.get("SYNCED_TABLE_UC_NAME").strip() or None
SYNCED_TABLE_UC_NAME = resolve_synced_table_uc_name(dbutils, _widget_synced)
print(f"SYNCED_TABLE_UC_NAME={SYNCED_TABLE_UC_NAME}")

# COMMAND ----------

count = refresh_cases_metadata(
    spark,
    bronze_table=BRONZE_TABLE,
    cases_metadata_table=CASES_METADATA_TABLE,
)
print(f"{CASES_METADATA_TABLE}: {count} rows")
display(spark.table(CASES_METADATA_TABLE))

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
table = w.database.get_synced_database_table(name=SYNCED_TABLE_UC_NAME)
pipeline_id = table.data_synchronization_status.pipeline_id
update = w.pipelines.start_update(pipeline_id=pipeline_id)
print(f"Triggered sync pipeline: {pipeline_id}")
print(f"Update id: {update.update_id}")

# COMMAND ----------

from notebook_hook import log_from_notebook  # noqa: E402

log_from_notebook(dbutils, "sync_cases", "success", row_count=count)
