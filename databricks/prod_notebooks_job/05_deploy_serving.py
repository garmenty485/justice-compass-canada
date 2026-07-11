# Databricks notebook source
# MAGIC %md
# MAGIC # Prod 05 — Deploy Model Serving
# MAGIC Register `justice_compass_rag` and update the serving endpoint after prod 01→03.

# COMMAND ----------

GOLD_TABLE = "gold_embeddings"
MODEL_NAME = "justice_compass_rag"
UC_ENTITY_NAME = "workspace.default.justice_compass_rag"
ENDPOINT_NAME = "justice-compass-rag-endpoint"
MODEL_VERSION = "1"
WORKLOAD_SIZE = "Small"
PROD_MARKER = "/databricks/prod_notebooks_job/"

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
if PROD_MARKER not in nb_path:
    raise RuntimeError(f"Unexpected notebook path: {nb_path}")
repo_rel = nb_path.split(PROD_MARKER)[0]
repo_root = repo_rel if repo_rel.startswith("/Workspace") else f"/Workspace{repo_rel}"
lakebase_dir = Path(repo_root) / "databricks" / "lakebase"
serving_dir = Path(repo_root) / "databricks" / "serving"
sys.path.insert(0, str(lakebase_dir))
sys.path.insert(0, str(serving_dir))

from secret_utils import secret_or_default  # noqa: E402

UC_ENTITY_NAME = secret_or_default(dbutils, "serving_uc_model_name", UC_ENTITY_NAME)
ENDPOINT_NAME = secret_or_default(dbutils, "serving_endpoint_name", ENDPOINT_NAME)
WORKLOAD_SIZE = secret_or_default(dbutils, "serving_workload_size", WORKLOAD_SIZE)
print(f"UC_ENTITY_NAME={UC_ENTITY_NAME}")
print(f"ENDPOINT_NAME={ENDPOINT_NAME}")
print(f"WORKLOAD_SIZE={WORKLOAD_SIZE}")

from justice_compass_rag import JusticeCompassRAG  # noqa: E402

print(f"Serving module: {serving_dir / 'justice_compass_rag.py'}")

# COMMAND ----------

import mlflow
import mlflow.pyfunc

count = spark.table(GOLD_TABLE).count()
if count == 0:
    raise RuntimeError(f"{GOLD_TABLE} is empty. Run prod 03 first.")

import pandas as pd
gold_pdf = pd.DataFrame(spark.table(GOLD_TABLE).toPandas())
local_parquet = "/tmp/gold_embeddings.parquet"
gold_pdf.to_parquet(local_parquet, index=False)

print(f"Gold rows exported: {count}")
print(f"Artifact path: {local_parquet}")

# COMMAND ----------

# MAGIC %md
# MAGIC Upgrade MLflow then **restartPython** so the new package is loaded.
# MAGIC Restart clears all Python variables — the next cell rehydrates config / paths / imports.

# COMMAND ----------

# MAGIC %pip install --upgrade 'mlflow>=2.13.1'
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# Rehydrate after restartPython() (kernel wipe)
from pathlib import Path
import sys

import pandas as pd
import mlflow
import mlflow.pyfunc
from mlflow.models import ModelSignature, infer_signature
from mlflow.types.schema import ColSpec, Schema

GOLD_TABLE = "gold_embeddings"
MODEL_NAME = "justice_compass_rag"
UC_ENTITY_NAME = "workspace.default.justice_compass_rag"
ENDPOINT_NAME = "justice-compass-rag-endpoint"
MODEL_VERSION = "1"
WORKLOAD_SIZE = "Small"
PROD_MARKER = "/databricks/prod_notebooks_job/"
local_parquet = "/tmp/gold_embeddings.parquet"

nb_path = (
    dbutils.notebook.entry_point.getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
if PROD_MARKER not in nb_path:
    raise RuntimeError(f"Unexpected notebook path: {nb_path}")
repo_rel = nb_path.split(PROD_MARKER)[0]
repo_root = repo_rel if repo_rel.startswith("/Workspace") else f"/Workspace{repo_rel}"
lakebase_dir = Path(repo_root) / "databricks" / "lakebase"
serving_dir = Path(repo_root) / "databricks" / "serving"
sys.path.insert(0, str(lakebase_dir))
sys.path.insert(0, str(serving_dir))

from secret_utils import secret_or_default  # noqa: E402

UC_ENTITY_NAME = secret_or_default(dbutils, "serving_uc_model_name", UC_ENTITY_NAME)
ENDPOINT_NAME = secret_or_default(dbutils, "serving_endpoint_name", ENDPOINT_NAME)
WORKLOAD_SIZE = secret_or_default(dbutils, "serving_workload_size", WORKLOAD_SIZE)

from justice_compass_rag import EMBED_MODEL, LLM_MODEL, JusticeCompassRAG  # noqa: E402

if not Path(local_parquet).exists():
    raise FileNotFoundError(
        f"{local_parquet} missing — re-run the gold export cell before this one."
    )

mlflow.set_registry_uri("databricks-uc")
serving_py = str(serving_dir / "justice_compass_rag.py")
print(f"Rehydrated serving_dir={serving_dir}")

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


with mlflow.start_run(run_name="justice-compass-rag-prod") as run:
    model_info = _log_pyfunc_model()
    run_id = run.info.run_id

print(f"Logged model: {model_info.model_uri}")
print(f"Run ID: {run_id}")

# COMMAND ----------

registered_name = UC_ENTITY_NAME
entity_version = MODEL_VERSION

try:
    result = mlflow.register_model(model_info.model_uri, UC_ENTITY_NAME)
    print(f"UC Registered: {result.name} version {result.version}")
    registered_name = result.name
    entity_version = str(result.version)
    model_uri = f"models:/{result.name}/{result.version}"
except Exception as exc:
    print(f"UC registration failed: {exc}")
    registered_name = MODEL_NAME
    entity_version = MODEL_VERSION
    model_uri = model_info.model_uri
    print(f"Fallback model URI: {model_uri}")

print(f"Name: {registered_name}, Version: {entity_version}")

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
    workload_size=WORKLOAD_SIZE,
    scale_to_zero=True,
)
print_deploy_result(result)

# COMMAND ----------

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
