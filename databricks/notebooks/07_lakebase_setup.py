# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Lakebase Setup
# MAGIC
# MAGIC 1. Create a **Lakebase project** (Free Edition: 1 project / account)
# MAGIC 2. Run `databricks/sql/lakebase_schema.sql` in Lakebase SQL Editor
# MAGIC 3. Register Lakebase in **Unity Catalog** (for cross-source queries from SQL warehouse)
# MAGIC 4. (Optional) Configure **Synced Tables** + **CDF** — see `docs/LAKEBASE.md`
# MAGIC
# MAGIC **Secrets** (secret scope `justice-compass`):
# MAGIC - `lakebase_host`, `lakebase_db`, `lakebase_user`, `lakebase_password`
# MAGIC
# MAGIC **Auth**：自訂 Postgres ROLE + **native PASSWORD**（非 OAuth）。Cloudflare Worker 使用同名參數（`LAKEBASE_*` secrets）。詳見 `docs/LAKEBASE.md` §連線與認證。
# MAGIC
# MAGIC Notebooks `01`–`03` and `05` call `pipeline_log.log_pipeline_run()` when secrets exist.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resolve repo path

# COMMAND ----------

from pathlib import Path

nb_path = (
    dbutils.notebook.entry_point.getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
repo_rel = nb_path.split("/databricks/notebooks/")[0]
repo_root = repo_rel if repo_rel.startswith("/Workspace") else f"/Workspace{repo_rel}"
schema_path = Path(repo_root) / "databricks" / "sql" / "lakebase_schema.sql"

print(f"Schema DDL file: {schema_path}")
if schema_path.exists():
    print(schema_path.read_text())
else:
    print("Schema file not found — Pull latest Git folder.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test pipeline_log (optional)
# MAGIC
# MAGIC Requires `%pip install psycopg2-binary` and Lakebase secrets.

# COMMAND ----------

# MAGIC %pip install psycopg2-binary --quiet

# COMMAND ----------

import sys

lakebase_dir = Path(repo_root) / "databricks" / "lakebase"
sys.path.insert(0, str(lakebase_dir))

from pipeline_log import log_pipeline_run  # noqa: E402

run_id = log_pipeline_run("gold", "success", row_count=0, dbutils=dbutils)
if run_id:
    print(f"Test insert OK: {run_id}")
else:
    print("Skipped — configure secret scope `justice-compass` Lakebase keys first.")
