# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Deploy Model Serving
# MAGIC Register `justice_compass_rag` pyfunc and create a serving endpoint for Cloudflare Worker.
# MAGIC
# MAGIC **Prerequisite**: Run `01` → `02` → `03` successfully.
# MAGIC
# MAGIC **After deploy**: copy invocation URL → Worker secrets (see `docs/DEPLOY_PHASE2.md`).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Config

# COMMAND ----------

GOLD_TABLE = "gold_embeddings"
MODEL_NAME = "justice_compass_rag"
UC_ENTITY_NAME = "workspace.default.justice_compass_rag"
ENDPOINT_NAME = "justice-compass-rag-endpoint"
MODEL_VERSION = "1"  # overwritten when UC register succeeds; 06 auto-picks latest

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resolve Git folder path

# COMMAND ----------

from pathlib import Path
import sys

nb_path = (
    dbutils.notebook.entry_point.getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
repo_rel = nb_path.split("/databricks/notebooks/")[0]
repo_root = repo_rel if repo_rel.startswith("/Workspace") else f"/Workspace{repo_rel}"
serving_dir = Path(repo_root) / "databricks" / "serving"
sys.path.insert(0, str(serving_dir))

from justice_compass_rag import EMBED_MODEL, LLM_MODEL, JusticeCompassRAG  # noqa: E402

print(f"Serving module: {serving_dir / 'justice_compass_rag.py'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Export Gold artifact
# MAGIC
# MAGIC Free Edition: **do not use `dbutils.fs`** — public DBFS is disabled.  
# MAGIC Write parquet on driver local disk; `mlflow.log_model` uploads it directly.

# COMMAND ----------

import mlflow
import mlflow.pyfunc

count = spark.table(GOLD_TABLE).count()
if count == 0:
    raise RuntimeError(f"{GOLD_TABLE} is empty. Run 03_gold_embed first.")

gold_pdf = spark.table(GOLD_TABLE).toPandas()

# Driver local path (not DBFS). /local_disk0 also works on serverless if /tmp fails.
local_parquet = "/tmp/gold_embeddings.parquet"
gold_pdf.to_parquet(local_parquet, index=False)

print(f"Gold rows exported: {count}")
print(f"Artifact path: {local_parquet}")

# COMMAND ----------

# DBTITLE 1,Upgrade MLflow for resources parameter
# MAGIC %pip install --upgrade 'mlflow>=2.13.1'
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log & register model
# MAGIC
# MAGIC Unity Catalog requires **model signature** at log time (input + output schema).

# COMMAND ----------

# DBTITLE 1,Log model with resource dependencies
import pandas as pd
from mlflow.models import ModelSignature, infer_signature
from mlflow.types.schema import ColSpec, Schema

mlflow.set_registry_uri("databricks-uc")

serving_py = str(serving_dir / "justice_compass_rag.py")

signature_input = pd.DataFrame(
    {"question": ["When can BC revoke a liquor licence?"]}
)
signature_output = pd.DataFrame(
    [
        {
            "answer": "Example answer based on context. This is not legal advice.",
            "citations": [
                {
                    "case_name": "Example Case",
                    "citation": "2021BCSC789",
                    "url": "https://example.com/case",
                    "snippet": "Example excerpt from liquor licensing case law.",
                }
            ],
            "mock": False,
        }
    ]
)

try:
    model_signature = infer_signature(signature_input, signature_output)
except Exception:
    model_signature = ModelSignature(
        inputs=Schema([ColSpec("string", "question")]),
        outputs=Schema(
            [
                ColSpec("string", "answer"),
                ColSpec("string", "citations"),
                ColSpec("boolean", "mock"),
            ]
        ),
    )

from mlflow.models.resources import DatabricksServingEndpoint  # noqa: E402

_log_kwargs = dict(
    artifact_path="model",
    python_model=JusticeCompassRAG(),
    artifacts={"gold_embeddings": local_parquet},
    pip_requirements=["mlflow>=2.13.1", "pandas", "pyarrow"],
    signature=model_signature,
    input_example=signature_input,
    # Auto-authentication passthrough: Databricks provisions a service principal
    # and rotates OAuth tokens for these endpoints — no manual DATABRICKS_TOKEN
    # env var needed on the serving endpoint, and it survives every re-deploy.
    resources=[
        DatabricksServingEndpoint(endpoint_name=EMBED_MODEL),
        DatabricksServingEndpoint(endpoint_name=LLM_MODEL),
    ],
)


def _log_pyfunc_model():
    """Free Edition MLflow varies: code_paths vs code_path (str or list)."""
    attempts = [
        {"code_path": [serving_py]},
        {"code_paths": [serving_py]},
        {"code_path": serving_py},
    ]
    last_type_error = None
    for extra in attempts:
        try:
            return mlflow.pyfunc.log_model(**_log_kwargs, **extra)
        except TypeError as exc:
            last_type_error = exc
            continue
    if last_type_error:
        raise last_type_error
    return mlflow.pyfunc.log_model(**_log_kwargs)


with mlflow.start_run(run_name="justice-compass-rag") as run:
    model_info = _log_pyfunc_model()
    run_id = run.info.run_id

print(f"Logged model: {model_info.model_uri}")
print(f"Run ID: {run_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Register to Unity Catalog (fallback: workspace registry)
# MAGIC
# MAGIC If UC register fails on Free Edition, use the `models:/` URI from the run directly in the endpoint UI.

# COMMAND ----------

registered_name = UC_ENTITY_NAME
entity_version = MODEL_VERSION

# Try UC registration; fall back to workspace registry if it fails
try:
    result = mlflow.register_model(model_info.model_uri, UC_ENTITY_NAME)
    print(f"✓ UC Registered: {result.name} version {result.version}")
    registered_name = result.name
    entity_version = str(result.version)
    model_uri = f"models:/{result.name}/{result.version}"
except Exception as exc:
    print(f"⚠ UC registration failed (common on Free Edition due to S3 permissions).")
    print(f"  Detail: {exc}")
    print(f"\n✓ Fallback: Using workspace registry URI directly.")
    # Use the workspace model URI from the logged run
    registered_name = MODEL_NAME
    entity_version = MODEL_VERSION
    model_uri = model_info.model_uri
    print(f"  Model URI: {model_uri}")
    print(f"\n→ Use this URI when creating the serving endpoint.")

print(f"\nFinal model reference:")
print(f"  Name: {registered_name}")
print(f"  Version: {entity_version}")
print(f"  URI: {model_uri}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create / update serving endpoint (REST API)
# MAGIC
# MAGIC Free Edition UI often fails with **Compute scale-out is required**.  
# MAGIC This cell uses REST API with explicit `workload_size: Small`.  
# MAGIC Re-run only this step via notebook **`06_create_serving_endpoint_api`**.

# COMMAND ----------

from create_endpoint_api import (  # noqa: E402
    create_or_update_serving_endpoint,
    print_deploy_result,
)

result = create_or_update_serving_endpoint(
    dbutils,
    endpoint_name=ENDPOINT_NAME,
    entity_name=UC_ENTITY_NAME,
    entity_version=entity_version,
    workload_size="Small",
    scale_to_zero=True,
)
print_deploy_result(result)

# COMMAND ----------

# Lakebase pipeline_runs (optional — see 07_lakebase_setup)
import sys
from pathlib import Path

sys.path.insert(0, str(serving_dir.parent / "lakebase"))
from notebook_hook import log_from_notebook  # noqa: E402

_serving_status = "success" if result.get("ok") else "failed"
_model_ver = int(entity_version) if str(entity_version).isdigit() else None
log_from_notebook(
    dbutils,
    "serving",
    _serving_status,
    row_count=_model_ver,
    error_message=None if result.get("ok") else str(result.get("error", ""))[:500],
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Invocation URL for Worker
# MAGIC
# MAGIC ```
# MAGIC https://<workspace-host>/serving-endpoints/justice-compass-rag-endpoint/invocations
# MAGIC ```
# MAGIC
# MAGIC ```bash
# MAGIC wrangler secret put DATABRICKS_SERVING_URL
# MAGIC wrangler secret put DATABRICKS_TOKEN   # Databricks PAT
# MAGIC cd cloudflare/worker && npx wrangler deploy
# MAGIC ```
