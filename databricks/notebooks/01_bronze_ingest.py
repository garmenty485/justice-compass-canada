# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingest
# MAGIC Load CanLII-style JSON from Git folder `data/sample/` into Delta `bronze_cases`.
# MAGIC
# MAGIC **Prerequisite**: Git folder cloned from `garmenty485/justice-compass` (Pull latest).

# COMMAND ----------

import json
from datetime import datetime, timezone
from pathlib import Path

BRONZE_TABLE = "bronze_cases"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resolve sample data path (Git folder)

# COMMAND ----------

def get_repo_root() -> Path:
    """Find justice-compass repo root from this notebook's path in a Git folder."""
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
    workspace_path = repo_rel if repo_rel.startswith("/Workspace") else f"/Workspace{repo_rel}"
    return Path(workspace_path)


repo_root = get_repo_root()
sample_dir = repo_root / "data" / "sample"
print(f"Repo root: {repo_root}")
print(f"Sample dir: {sample_dir}")

json_files = sorted(sample_dir.glob("*.json"))
if not json_files:
    raise FileNotFoundError(
        f"No JSON files in {sample_dir}. Git Pull the repo or check the path."
    )
print(f"Found {len(json_files)} sample case files")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Ingest to Bronze (Delta)

# COMMAND ----------

rows = []
for path in json_files:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    case_id = doc.get("caseId", {})
    if isinstance(case_id, dict):
        case_id_str = case_id.get("caseId") or path.stem
    else:
        case_id_str = str(case_id)
    rows.append(
        {
            "case_id": case_id_str,
            "citation": doc.get("citation"),
            "title": doc.get("title"),
            "court": doc.get("court"),
            "decision_date": doc.get("decisionDate"),
            "canlii_url": doc.get("url"),
            "full_text": doc.get("fullText"),
            "keywords": doc.get("keywords") or [],
            "topics": doc.get("topics") or [],
            "source_file": path.name,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
    )

df = spark.createDataFrame(rows)
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    BRONZE_TABLE
)

count = spark.table(BRONZE_TABLE).count()
print(f"Ingested {count} cases → {BRONZE_TABLE}")
display(spark.table(BRONZE_TABLE).select("case_id", "citation", "title", "court"))

# COMMAND ----------

# Lakebase pipeline_runs (optional — see 07_lakebase_setup)
import sys
from pathlib import Path

_lakebase = Path(repo_root) / "databricks" / "lakebase"
sys.path.insert(0, str(_lakebase))
from notebook_hook import log_from_notebook  # noqa: E402

log_from_notebook(dbutils, "bronze", "success", row_count=count)
