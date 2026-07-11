# Databricks notebook source
# MAGIC %md
# MAGIC # Prod 03 — Gold Embed
# MAGIC Embed `silver_chunks` with Foundation Model `ai_query`, write `gold_embeddings`.

# COMMAND ----------

SILVER_TABLE = "silver_chunks"
GOLD_TABLE = "gold_embeddings"
EMBED_MODEL = "databricks-gte-large-en"
PROD_MARKER = "/databricks/prod_notebooks_job/"

# COMMAND ----------

silver_count = spark.table(SILVER_TABLE).count()
if silver_count == 0:
    raise RuntimeError(f"{SILVER_TABLE} is empty. Run prod 02 first.")
print(f"Silver chunks to embed: {silver_count}")

# COMMAND ----------

from pyspark.sql.functions import expr

try:
    gold_df = (
        spark.table(SILVER_TABLE)
        .select(
            "chunk_id",
            "case_id",
            "citation",
            "title",
            "court",
            "canlii_url",
            "chunk_index",
            "chunk_text",
            expr(f"ai_query('{EMBED_MODEL}', chunk_text)").alias("embedding"),
        )
    )
    gold_df.limit(1).collect()
except Exception as e:
    raise RuntimeError(
        f"ai_query embedding failed with model '{EMBED_MODEL}'. "
        f"Original error: {e}"
    ) from e

gold_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    GOLD_TABLE
)

count = spark.table(GOLD_TABLE).count()
dim = len(spark.table(GOLD_TABLE).select("embedding").first().embedding)
print(f"Gold embeddings: {count} rows, dim={dim} → {GOLD_TABLE}")
display(spark.table(GOLD_TABLE).select("chunk_id", "case_id", "citation", "chunk_index"))

# COMMAND ----------

import sys
from pathlib import Path

_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_rel = _nb.split(PROD_MARKER)[0]
_root = _rel if _rel.startswith("/Workspace") else f"/Workspace{_rel}"
sys.path.insert(0, str(Path(_root) / "databricks" / "lakebase"))
from notebook_hook import log_from_notebook  # noqa: E402

log_from_notebook(dbutils, "gold", "success", row_count=count)
