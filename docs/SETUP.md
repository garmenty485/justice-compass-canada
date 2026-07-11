# Account Setup Checklist

Complete these before Phase 1. All free tiers unless noted.

## 1. GitHub (Private repo)

- [x] Create repo `[garmenty485/justice-compass](https://github.com/garmenty485/justice-compass)` (Private)
- [x] Push local code
- [x] Enable Actions
- [ ] Add secrets when ready:
  - `GEMINI_API_KEY` (Phase 4) — ✅ key in GitHub Secrets；`ai-pr-review.yml` 已就緒
  - `CLOUDFLARE_API_TOKEN` (Phase 3 CD deploy) — ✅ Pages + Worker CD

## 2. Cloudflare (Free)

- [x] Sign up
- [x] Wrangler login + deploy Worker
- [x] **Worker URL**: `https://justice-compass-api.justicebrobro.workers.dev`
- [x] Create **Pages** project → connect GitHub → build output: `cloudflare/pages` — Phase 2 ✅
- [x] Worker live RAG：`DATABRICKS_SERVING_URL` + `DATABRICKS_TOKEN` — Phase 2 ✅

Verify:

```bash
curl https://justice-compass-api.justicebrobro.workers.dev/health
curl "https://justice-compass-api.justicebrobro.workers.dev/query?q=liquor+licence"
```



## 3. Databricks Free Edition

- [x] Sign up
- [x] **Git folder** cloned from `garmenty485/justice-compass`
- [x] Pull latest after each `git push`
- [x] Run `01_bronze_ingest` → `bronze_cases` (4 rows)
- [x] Run `02_silver_transform` → `silver_chunks` (5 chunks)
- [x] Run `03_gold_embed` → `gold_embeddings`
- [x] Run `04_rag_serving` → notebook RAG demo
- [x] Run **`05_deploy_serving`** → Model Serving endpoint **Ready**（Free Edition REST API 路徑，見 [`docs/DEPLOY_PHASE2.md`](DEPLOY_PHASE2.md)）
- [x] **Lakebase**（Free Edition：1 project，**必做**）→ project + schema + UC 註冊 ✅；見 [`docs/LAKEBASE.md`](LAKEBASE.md)
- [x] **Lakebase 認證**：自訂 Postgres ROLE + native PASSWORD（**非 OAuth**）；secrets 已設定於 Databricks `justice-compass` scope **與** Cloudflare Worker ✅
- [x] **AI Search** — **不做**；RAG 用 Delta cosine + Model Serving（已驗收）
- [x] **Jobs**（Free Edition：最多 5 concurrent tasks，**必做**）→ **`08`** + Run now **01→03** ✅；見 [`docs/JOBS.md`](JOBS.md)

**Free Edition 配額**（2026-06 更新）：已含 Lakebase / AI Search / Jobs，詳見 [官方限制](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)。

**Free Edition 儲存（勿用 FileStore / Public DBFS）**

| 用途 | 正確做法 | 勿用（Phase 0 舊流程） |
|------|----------|------------------------|
| Sample JSON | Git folder `data/sample/` | `/FileStore/justice-compass/sample/` 手動 upload |
| Medallion 表 | Delta `bronze_cases` 等 | 透過 DBFS 搬 JSON |
| Serving artifact | driver `/tmp/*.parquet` + MLflow | `dbutils.fs.cp` 到 DBFS |

**Git folder workflow**

1. Edit locally → `git push`
2. Databricks Git folder → **Pull**
3. Run notebooks `01` → `05` in order

**Phase 3 freshness** ✅：首頁 **Model / Docs last updated** via Worker `/meta` + UC Lakebase — see `docs/LAKEBASE.md`.



## 4. Google AI Studio (Gemini — Free)

- [x] Get API key: [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- [x] Add to GitHub Secrets as `GEMINI_API_KEY`



## 5. Demo corpus (synthetic)

- [x] **8 synthetic cases** in `data/sample/` — BC liquor licensing themes (not live CanLII)
- [ ] After edits: Databricks `01`→`03`→`05` + `09` sync to Lakebase `cases`

> Corpus is portfolio MVP only. Citations in live RAG come from **Gold retrieval**, not Lakebase reads.

Secrets 總覽見 [`docs/secrets_map.md`](secrets_map.md)。



## Cursor + Cloudflare MCP

`.cursor/mcp.json` includes Cloudflare MCP servers ([official setup](https://developers.cloudflare.com/agent-setup/prompt.md)). **Restart Cursor** after first open; OAuth triggers on first Cloudflare tool use.

## Local verify

```bash
npm install --prefix cloudflare/worker
npm test
npm run dev:worker
# Pages: open cloudflare/pages/index.html (localhost uses Worker on :8787)
```

