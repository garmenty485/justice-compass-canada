# Phase 2 — Deploy Live RAG (Databricks → Worker → Pages)

## Overview

```
Browser (Pages) → Worker → Model Serving endpoint → justice_compass_rag pyfunc
```

Notebook `04` = dev/demo inside Databricks.  
Notebook `05` = register pyfunc + create serving endpoint for Cloudflare.

> **2026-07-05 更新**：Free Edition 上 **`05_deploy_serving` 已成功建立 endpoint**（commit `0a5acab`，Databricks AI 修復）。路徑：driver `/tmp` parquet → MLflow log → UC 或 workspace registry fallback → REST API + `workload_size: Small`。

---

## Step 1 — Databricks (Git folder Pull → Run `05_deploy_serving`)

1. Pull latest `dev` branch（含 `0a5acab` 或更新）
2. Run pipelines `01`–`03` if tables are stale
3. Run **`05_deploy_serving`** → **Run all**（順序：Export → MLflow upgrade → Log → Register → Endpoint）

**`05` 內建 Free Edition 修復**（無需手改）：

| 步驟 | 做法 |
|------|------|
| Gold export | driver `/tmp/gold_embeddings.parquet`（不用 `dbutils.fs` / DBFS） |
| MLflow | cell：`%pip install --upgrade 'mlflow>=2.11.0'` + `restartPython()` |
| Register | 先試 UC `workspace.default.justice_compass_rag`；S3 權限失敗則 fallback workspace `models:/...` URI |
| Endpoint | REST API，`served_entities` 失敗自動試 `served_models` + `workload_size: Small` |

4. 若 endpoint cell 單獨失敗，重跑 **`06_create_serving_endpoint_api`**（會自動用 UC 最新 version，例如 v6）

**Free Edition UI bug**: Creating endpoint in Serving UI may show `Compute scale-out is required` (no Small/Medium field). Use notebook **`06`** or the REST API cell in **`05`** instead.

If API create still fails:

1. Check **Build logs** on the endpoint page
2. Confirm model exists — UC name `workspace.default.justice_compass_rag` **或** workspace registry URI（register cell 印出的 `model_uri`）
3. Wait until endpoint status = **Ready** (cold start may take several minutes)
4. Inference 時 pyfunc 需呼叫 Foundation Model — `justice_compass_rag.py` 已在 Serving 環境設 `MLFLOW_TRACKING_URI=databricks`

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
2. Connect GitHub → `garmenty485/justice-compass` → branch `dev`
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

Add repo secret `CLOUDFLARE_API_TOKEN`, push to `dev` — workflow `.github/workflows/deploy-pages.yml`.

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
| UC register S3 / permission error | **`05`** fallback — 用 workspace `model_uri`，endpoint 仍可用 |
| FM auth in Serving container | Fixed — `_deploy_client()` sets `MLFLOW_TRACKING_URI=databricks` + MLflow version fallback |
| `resources` param on log_model | **勿用** — MLflow 3.x UC bug；改 env auth（見 `05` 註解） |
| Hardcoded model constants in `create_endpoint_api.py` | 已移除 — endpoint 參數由 **`05`/`06` config cell 傳入** |
| CORS error from Pages | Worker already sets `Access-Control-Allow-Origin: *` |

---

## Phase 2 done when

- [x] Databricks endpoint **Ready** + invocations curl 有真實 answer
- [x] `curl Worker/query` returns `"mock": false`
- [x] Pages URL loads UI and shows real citations
- [x] Phase 2 驗收完成

**Next**: Lakebase + Jobs — 詳見 `#016`（Lake↔Base 亮點、05/06 自動化、首頁 freshness）
