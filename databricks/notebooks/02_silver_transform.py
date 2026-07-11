# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver Transform
# MAGIC Read `bronze_cases`, chunk `full_text`, write `silver_chunks`.
# MAGIC
# MAGIC **Prerequisite**: Run `01_bronze_ingest` first.

# COMMAND ----------

BRONZE_TABLE = "bronze_cases"
SILVER_TABLE = "silver_chunks"
CHUNK_SIZE = 800      # ~512 tokens (char approximation)
CHUNK_OVERLAP = 128   # ~64 tokens

# COMMAND ----------

# MAGIC %md
# MAGIC ## Chunk helper

# COMMAND ----------

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping character chunks."""
    if not text or not text.strip():
        return []
    text = " ".join(text.split())
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


bronze_count = spark.table(BRONZE_TABLE).count()
if bronze_count == 0:
    raise RuntimeError(f"{BRONZE_TABLE} is empty. Run 01_bronze_ingest first.")
print(f"Bronze rows: {bronze_count}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Transform to Silver

# COMMAND ----------

silver_rows = []
for row in spark.table(BRONZE_TABLE).collect():
    pieces = chunk_text(row.full_text or "", CHUNK_SIZE, CHUNK_OVERLAP)
    if not pieces:
        pieces = [(row.full_text or row.title or "")[:CHUNK_SIZE]]
    for idx, piece in enumerate(pieces):
        silver_rows.append(
            {
                "chunk_id": f"{row.case_id}_{idx}",
                "case_id": row.case_id,
                "citation": row.citation,
                "title": row.title,
                "court": row.court,
                "canlii_url": row.canlii_url,
                "chunk_index": idx,
                "chunk_text": piece,
                "keywords": row.keywords,
                "topics": row.topics,
            }
        )

silver_df = spark.createDataFrame(silver_rows)
silver_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    SILVER_TABLE
)

count = spark.table(SILVER_TABLE).count()
print(f"Silver chunks: {count} → {SILVER_TABLE}")
display(spark.table(SILVER_TABLE).select("chunk_id", "case_id", "citation", "chunk_index"))

# COMMAND ----------

# Lakebase pipeline_runs (optional — see 07_lakebase_setup)
import sys
from pathlib import Path

_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_rel = _nb.split("/databricks/notebooks/")[0]
_root = _rel if _rel.startswith("/Workspace") else f"/Workspace{_rel}"
sys.path.insert(0, str(Path(_root) / "databricks" / "lakebase"))
from notebook_hook import log_from_notebook  # noqa: E402

log_from_notebook(dbutils, "silver", "success", row_count=count)
