# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Create Serving Endpoint (REST API)
# MAGIC
# MAGIC **Use when**: `05_deploy_serving` logged the model but UI fails with  
# MAGIC `Compute scale-out is required` (Free Edition UI bug).
# MAGIC
# MAGIC **Prerequisite**: UC model `workspace.default.justice_compass_rag` with at least one version (from `05` register cell).
# MAGIC
# MAGIC Sets explicit `workload_size: Small` via REST API — community workaround.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Config

# COMMAND ----------

ENDPOINT_NAME = "justice-compass-rag-endpoint"
UC_ENTITY_NAME = "workspace.default.justice_compass_rag"
ENTITY_VERSION = "1"  # overwritten below by latest UC version
WORKLOAD_SIZE = "Small"
SCALE_TO_ZERO = True

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resolve latest UC version (optional)

# COMMAND ----------

import mlflow

mlflow.set_registry_uri("databricks-uc")
client = mlflow.MlflowClient()

versions = client.search_model_versions(f"name='{UC_ENTITY_NAME}'")
if not versions:
    raise RuntimeError(
        f"No UC versions for {UC_ENTITY_NAME}. "
        "Run 05_deploy_serving → Log & register (with signature) first."
    )

latest = max(versions, key=lambda v: int(v.version))
ENTITY_VERSION = str(latest.version)
print(f"Using UC version: {ENTITY_VERSION} (status: {latest.status})")
print("All versions:", [(v.version, v.status) for v in sorted(versions, key=lambda v: int(v.version))])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create or update endpoint via API

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

from create_endpoint_api import (  # noqa: E402
    create_or_update_serving_endpoint,
    print_deploy_result,
)

result = create_or_update_serving_endpoint(
    dbutils,
    endpoint_name=ENDPOINT_NAME,
    entity_name=UC_ENTITY_NAME,
    entity_version=ENTITY_VERSION,
    workload_size=WORKLOAD_SIZE,
    scale_to_zero=SCALE_TO_ZERO,
)

print_deploy_result(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next: Worker secrets
# MAGIC
# MAGIC ```bash
# MAGIC wrangler secret put DATABRICKS_SERVING_URL
# MAGIC wrangler secret put DATABRICKS_TOKEN
# MAGIC cd cloudflare/worker && npx wrangler deploy
# MAGIC ```
# MAGIC
# MAGIC Test:
# MAGIC ```bash
# MAGIC curl -X POST "$DATABRICKS_SERVING_URL" \
# MAGIC   -H "Authorization: Bearer $DATABRICKS_TOKEN" \
# MAGIC   -H "Content-Type: application/json" \
# MAGIC   -d '{"inputs":{"question":["When can BC revoke a liquor licence?"]}}'
# MAGIC ```