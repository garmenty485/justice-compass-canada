# Account Setup Checklist

Complete these before Phase 1. All free tiers unless noted.

## 1. GitHub (Private repo)

- [x] Create repo `[garmenty485/justice-compass](https://github.com/garmenty485/justice-compass)` (Private)
- [x] Push local code
- [x] Enable Actions
- [ ] Add secrets when ready:
  - `GEMINI_API_KEY` (Phase 4) — ✅ key in GitHub Secrets; `ai-pr-review.yml` ready
  - `CLOUDFLARE_API_TOKEN` (Phase 3 CD deploy) — ✅ Pages + Worker CD

## 2. Cloudflare (Free)

- [x] Sign up
- [x] Wrangler login + deploy Worker
- [x] **Worker URL**: `https://justice-compass-api.justicebrobro.workers.dev`
- [x] Create **Pages** project → connect GitHub → build output: `cloudflare/pages` — Phase 2 ✅
- [x] Worker live RAG: `DATABRICKS_SERVING_URL` + `DATABRICKS_TOKEN` — Phase 2 ✅

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
- [x] Run **`05_deploy_serving`** → Model Serving endpoint **Ready** (Free Edition REST API path, see [`docs/DEPLOY_PHASE2.md`](DEPLOY_PHASE2.md))
- [x] **Lakebase** (Free Edition: 1 project, **required**) → project + schema + UC registration ✅; see [`docs/LAKEBASE.md`](LAKEBASE.md)
- [x] **Lakebase auth**: custom Postgres ROLE + native PASSWORD (**not OAuth**); secrets configured in the Databricks `justice-compass` scope **and** the Cloudflare Worker ✅
- [x] **AI Search** — **not used**; RAG uses Delta cosine + Model Serving (verified)
- [x] **Jobs** (Free Edition: up to 5 concurrent tasks, **required**) → **`08`** + Run now **01→03** ✅; see [`docs/JOBS.md`](JOBS.md)

**Free Edition quotas** (updated 2026-06): now includes Lakebase / AI Search / Jobs — see [official limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations).

**Free Edition storage (avoid FileStore / public DBFS)**

| Purpose | Correct approach | Avoid (legacy Phase 0 flow) |
|------|----------|------------------------|
| Sample JSON | Git folder `data/sample/` | Manual upload to `/FileStore/justice-compass/sample/` |
| Medallion tables | Delta `bronze_cases`, etc. | Moving JSON through DBFS |
| Serving artifact | driver `/tmp/*.parquet` + MLflow | `dbutils.fs.cp` to DBFS |

**Git folder workflow**

1. Edit locally → `git push`
2. Databricks Git folder → **Pull**
3. Run notebooks `01` → `05` in order

**Phase 3 freshness** ✅: homepage **Model / Docs last updated** via Worker `/meta` + UC Lakebase — see `docs/LAKEBASE.md`.



## 4. Google AI Studio (Gemini — Free)

- [x] Get API key: [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- [x] Add to GitHub Secrets as `GEMINI_API_KEY`



## 5. Demo corpus (synthetic)

- [x] **8 synthetic cases** in `data/sample/` — BC liquor licensing themes (not live CanLII)
- [ ] After edits: Databricks `01`→`03`→`05` + `09` sync to Lakebase `cases`

> Corpus is portfolio MVP only. Citations in live RAG come from **Gold retrieval**, not Lakebase reads.

See [`docs/secrets_map.md`](secrets_map.md) for the full secrets overview.



## Cursor + Cloudflare MCP

`.cursor/mcp.json` includes Cloudflare MCP servers ([official setup](https://developers.cloudflare.com/agent-setup/prompt.md)). **Restart Cursor** after first open; OAuth triggers on first Cloudflare tool use.

## Local verify

```bash
npm install --prefix cloudflare/worker
npm test
npm run dev:worker
# Pages: open cloudflare/pages/index.html (localhost uses Worker on :8787)
```

