# Phase 2 — Deploy Live RAG (Databricks → Worker → Pages)

## Overview

```
Browser (Pages) → Worker → Model Serving endpoint → justice_compass_rag pyfunc
```

Notebook `04` = dev/demo inside Databricks.  
Notebook `05` = register pyfunc + create serving endpoint for Cloudflare.

> **Update (2026-07-05)**: On Free Edition, **`05_deploy_serving` successfully creates the endpoint** (commit `0a5acab`, fixed with Databricks AI assistance). Path: driver `/tmp` parquet → MLflow log → UC or workspace registry fallback → REST API + `workload_size: Small`.

---

## Step 1 — Databricks (Git folder Pull → Run `05_deploy_serving`)

1. Pull latest `main` branch
2. Run pipelines `01`–`03` if tables are stale
3. Run **`05_deploy_serving`** → **Run all** (order: Export → MLflow upgrade → Log → Register → Endpoint)

**`05` has Free Edition fixes built in** (no manual changes needed):

| Step | Approach |
|------|------|
| Gold export | driver `/tmp/gold_embeddings.parquet` (no `dbutils.fs` / DBFS) |
| MLflow | cell: `%pip install --upgrade 'mlflow>=2.11.0'` + `restartPython()` |
| Register | Try UC `workspace.default.justice_compass_rag` first; on S3 permission failure, fall back to the workspace `models:/...` URI |
| Endpoint | REST API; if `served_entities` fails it automatically tries `served_models` + `workload_size: Small` |

4. If the endpoint cell fails on its own, rerun **`06_create_serving_endpoint_api`** (it automatically uses the latest UC version, e.g. v6)

**Free Edition UI bug**: Creating endpoint in Serving UI may show `Compute scale-out is required` (no Small/Medium field). Use notebook **`06`** or the REST API cell in **`05`** instead.

If API create still fails:

1. Check **Build logs** on the endpoint page
2. Confirm the model exists — UC name `workspace.default.justice_compass_rag` **or** the workspace registry URI (the `model_uri` printed by the register cell)
3. Wait until endpoint status = **Ready** (cold start may take several minutes)
4. At inference time, the pyfunc needs to call the Foundation Model — `justice_compass_rag.py` already sets `MLFLOW_TRACKING_URI=databricks` in the Serving environment

Copy **invocation URL**, e.g.:

```text
https://<workspace-host>/serving-endpoints/justice-compass-rag-endpoint/invocations
```

Test in Databricks or curl:

```bash
curl -X POST "$DATABRICKS_SERVING_URL" \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"inputs":{"question":["When can BC revoke a liquor licence?"]}}'
```

---

## Step 2 — Cloudflare Worker secrets

From WSL:

```bash
cd /home/ken/JD-project/cloudflare/worker
npx wrangler secret put DATABRICKS_SERVING_URL
# paste full .../invocations URL

npx wrangler secret put DATABRICKS_TOKEN
# paste Databricks PAT (Settings → Developer → Access tokens)

npx wrangler deploy
```

Verify live (no mock):

```bash
curl "https://justice-compass-api.justicebrobro.workers.dev/health"
# databricks_configured: true

curl "https://justice-compass-api.justicebrobro.workers.dev/query?q=liquor+licence+revoke"
# mock: false, real answer + citations
```

---

## Step 3 — Cloudflare Pages (frontend)

### Option A — Dashboard (recommended first time)

1. Cloudflare Dashboard → **Workers & Pages** → **Create** → **Pages**
2. Connect GitHub → your fork → branch `main`
3. Build settings:
   - **Framework preset**: None
   - **Build command**: (leave empty)
   - **Build output directory**: `cloudflare/pages`
4. Deploy → open Pages URL → search should hit live Worker

### Option B — Wrangler CLI

```bash
npx wrangler pages project create justice-compass
npx wrangler pages deploy ../pages --project-name=justice-compass
```

### Option C — GitHub Actions

Add repo secret `CLOUDFLARE_API_TOKEN`, push to `main` — workflow `.github/workflows/deploy-pages.yml`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `[DBFS_DISABLED]` on `05` | Fixed in repo — Pull latest; export uses driver `/tmp/` only, no `dbutils.fs` |
| `unexpected keyword argument 'code_paths'` | Fixed — `_log_pyfunc_model()` tries `code_path=[file]` first |
| `code_path should be a list, not str` | Same fix — list form tried before str |
| Worker still `mock: true` | Secrets not set or wrong URL (must end with `/invocations`) |
| Serving 403 | PAT missing **CAN QUERY** on endpoint |
| Serving timeout | Cold start; retry after 60s (scale-to-zero) |
| Free Edition endpoint create fails | Run **`06_create_serving_endpoint_api`** (REST API + `workload_size: Small`) |
| `Model version '1' does not exist` | Run **`05`** Log & register with signature first; then **`06`** |
| UC register / no signature | Fixed in **`05`** — `log_model` includes `signature` + `input_example` |
| UC register S3 / permission error | **`05`** falls back to the workspace `model_uri`; the endpoint still works |
| FM auth in Serving container | Fixed — `_deploy_client()` sets `MLFLOW_TRACKING_URI=databricks` + MLflow version fallback |
| `resources` param on log_model | **Do not use** — MLflow 3.x UC bug; use env auth instead (see `05` comments) |
| Hardcoded model constants in `create_endpoint_api.py` | Removed — endpoint parameters are now passed in via the **`05`/`06` config cell** |
| CORS error from Pages | Worker already sets `Access-Control-Allow-Origin: *` |

---

## Phase 2 done when

- [x] Databricks endpoint **Ready** + invocations curl returns a real answer
- [x] `curl Worker/query` returns `"mock": false`
- [x] Pages URL loads UI and shows real citations
- [x] Phase 2 verified complete

**Next**: Lakebase + Jobs — see `docs/LAKEBASE.md` and `docs/JOBS.md` (Lake↔Base highlights, 05/06 automation, homepage freshness)
