# Databricks notebook source
# MAGIC %md
# MAGIC # 10 — Lakebase CDF: query_logs → Delta audit (Base → Lake)
# MAGIC
# MAGIC **Goal**: Stream `query_logs` changes to Unity Catalog Delta (`lb_query_logs_history`).
# MAGIC
# MAGIC **Prerequisite**:
# MAGIC - Worker writes to `query_logs` (deploy Worker with `LAKEBASE_*` secrets) ✅
# MAGIC - Workspace admin enabled **Lakebase Change Data Feed** preview
# MAGIC - Lakebase project on **Postgres 17 / Autoscaling**
# MAGIC
# MAGIC **Known issue (2026-07-06)**: CDF UI configured + `REPLICA IDENTITY FULL` set, but
# MAGIC `lb_query_logs_history` Delta table may **not appear** on Free Edition (platform preview bug).
# MAGIC Audit still works via Lakebase `query_logs` directly. See `docs/LAKEBASE.md` §CDF 驗收狀態.
# MAGIC
# MAGIC Docs: https://docs.databricks.com/aws/en/oltp/projects/lakebase-cdf

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Replica identity (required for CDF)

# COMMAND ----------

# Run in Lakebase SQL Editor or via psycopg2 if your role has DDL rights:
#
#   ALTER TABLE query_logs REPLICA IDENTITY FULL;
#
# Verify:
#   SELECT relname, relreplident FROM pg_class c
#   JOIN pg_namespace n ON n.oid = c.relnamespace
#   WHERE n.nspname = 'public' AND c.relname = 'query_logs';

print("Run ALTER TABLE query_logs REPLICA IDENTITY FULL; in Lakebase SQL Editor.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Start CDF in Lakebase UI
# MAGIC
# MAGIC 1. App switcher → **Lakebase Postgres** → your project → branch
# MAGIC 2. **Branch overview** → **Change Data Feed** tab
# MAGIC 3. **Start** — source schema `public`, pick destination UC catalog + schema
# MAGIC 4. Destination table name pattern: **`lb_query_logs_history`**
# MAGIC 5. Status should become **Streaming** after initial snapshot
# MAGIC
# MAGIC Inspect in Lakebase:
# MAGIC `SELECT * FROM wal2delta.tables;`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Verify Delta audit table (after CDF Online)

# COMMAND ----------

DEST_CATALOG = "justice_compass_lakebase"  # adjust to your destination catalog
DEST_SCHEMA = "default"  # adjust
HISTORY_TABLE = f"{DEST_CATALOG}.{DEST_SCHEMA}.lb_query_logs_history"

try:
    n = spark.table(HISTORY_TABLE).count()
    print(f"{HISTORY_TABLE}: {n} change rows")
    display(spark.table(HISTORY_TABLE).orderBy("_timestamp", ascending=False).limit(10))
except Exception as exc:
    print(f"Not ready yet — configure CDF in Lakebase UI first. ({exc})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo query — recent audit events

# COMMAND ----------

try:
    spark.sql(
        f"""
        SELECT _pg_change_type, question, mock_mode, latency_ms, _timestamp
        FROM {HISTORY_TABLE}
        WHERE _pg_change_type IN ('insert', 'update_postimage')
        ORDER BY _timestamp DESC
        LIMIT 20
        """
    ).show(truncate=False)
except Exception as exc:
    print(f"Skip demo query until CDF destination exists. ({exc})")
