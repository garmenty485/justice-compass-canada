# Databricks notebook source
# MAGIC %md
# MAGIC # 09 — Synced Tables: cases_metadata → Lakebase (Lake → Base)
# MAGIC
# MAGIC **Goal**: Serve case metadata from Lakehouse through Lakebase for low-latency reads.
# MAGIC
# MAGIC **Paths**:
# MAGIC 1. **Primary (platform-native)**: Unity Catalog **Synced Table** from `workspace.default.cases_metadata` → Postgres
# MAGIC 2. **Fallback**: `sync_cases.py` upsert into Lakebase `cases` (same shape, for immediate demo)
# MAGIC
# MAGIC **Prerequisite**: Run `01` (bronze) first; Lakebase secrets in scope `justice-compass`.

# COMMAND ----------

UC_CATALOG = "workspace"
UC_SCHEMA = "default"
BRONZE_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.bronze_cases"
CASES_METADATA_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.cases_metadata"
SYNCED_TABLE_UC_NAME = None  # e.g. "workspace.default.cases_meta_synced" after UI create

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Build Delta source `cases_metadata`
# MAGIC
# MAGIC Uses INSERT OVERWRITE after first create — preserves Delta table ID for Synced Tables.

# COMMAND ----------

from pathlib import Path
import sys

_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_rel = _nb.split("/databricks/notebooks/")[0]
_root = _rel if _rel.startswith("/Workspace") else f"/Workspace{_rel}"
sys.path.insert(0, str(Path(_root) / "databricks" / "lakebase"))

from cases_metadata import refresh_cases_metadata  # noqa: E402

count = refresh_cases_metadata(
    spark,
    bronze_table=BRONZE_TABLE,
    cases_metadata_table=CASES_METADATA_TABLE,
)
print(f"{CASES_METADATA_TABLE}: {count} rows")
display(spark.table(CASES_METADATA_TABLE))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. CDF
# MAGIC
# MAGIC Enabled idempotently inside `refresh_cases_metadata` (Triggered / Continuous sync).

# COMMAND ----------

print(f"CDF enabled on {CASES_METADATA_TABLE} (via refresh_cases_metadata)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create Synced Table (UI — recommended on Free Edition)
# MAGIC
# MAGIC 1. **Catalog** → open **`workspace.default.cases_metadata`**
# MAGIC 2. **Create** → **Synced table**
# MAGIC 3. Database type: **Lakebase Serverless (Autoscaling)** → your project / branch / DB
# MAGIC 4. Sync mode: **Triggered** (CDF enabled above)
# MAGIC 5. Primary key: **`case_id`**
# MAGIC 6. Suggested synced table name: **`cases_meta_synced`**
# MAGIC 7. After status **Online**, query in Lakebase SQL Editor:
# MAGIC    `SELECT count(*) FROM "default".cases_meta_synced;`
# MAGIC
# MAGIC Docs: https://docs.databricks.com/aws/en/oltp/projects/sync-tables

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Fallback — upsert into Lakebase `cases` (psycopg2)
# MAGIC
# MAGIC Use until Synced Table is Online, or for the manual `cases` table in `lakebase_schema.sql`.

# COMMAND ----------

sys.path.insert(0, str(Path(_root) / "databricks" / "lakebase"))
from sync_cases import upsert_cases_from_spark  # noqa: E402

synced = upsert_cases_from_spark(spark, CASES_METADATA_TABLE, dbutils=dbutils)
print(f"Fallback upsert rows: {synced}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Optional — trigger Synced Table pipeline (after UI create)
# MAGIC
# MAGIC Set `SYNCED_TABLE_UC_NAME` at top to your three-part synced table name, then run this cell.

# COMMAND ----------

if SYNCED_TABLE_UC_NAME:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    table = w.database.get_synced_database_table(name=SYNCED_TABLE_UC_NAME)
    pipeline_id = table.data_synchronization_status.pipeline_id
    w.pipelines.start_update(pipeline_id=pipeline_id)
    print(f"Triggered sync pipeline: {pipeline_id}")
else:
    print("Set SYNCED_TABLE_UC_NAME after creating Synced Table in Catalog UI.")
