# Secrets Map

> 本專案各組件資料流與所需 secrets / keys 一覽。  
> 設定細節見 [SETUP.md](SETUP.md)、[DEPLOY_PHASE2.md](DEPLOY_PHASE2.md)、[LAKEBASE.md](LAKEBASE.md)、[`.env.example`](../.env.example)。

---

## Flow + Secrets

```mermaid
flowchart LR
    subgraph local["本機開發"]
        devvars["worker/.dev.vars"]
    end

    subgraph gh["GitHub Actions"]
        gha["CI / Deploy / AI Review"]
    end

    subgraph cf["Cloudflare"]
        pages["Pages<br/>(無 secrets)"]
        worker["Worker"]
    end

    subgraph dbx["Databricks"]
        serving["Model Serving<br/>(RAG)"]
        meta["MLflow + SQL Warehouse<br/>(/meta)"]
        notebooks["Notebooks / Jobs"]
        lakebase["Lakebase Postgres"]
    end

    sample["data/sample JSON"]

    user["使用者"] --> pages
    pages --> worker
    worker -->|"DATABRICKS_SERVING_URL<br/>DATABRICKS_TOKEN"| serving
    worker -->|"WAREHOUSE_ID<br/>PIPELINE_RUNS_TABLE"| meta
    worker -->|"LAKEBASE_HOST/DB/USER/PASSWORD"| lakebase

    sample --> notebooks
    devvars --> worker
    gha -->|"CLOUDFLARE_API_TOKEN"| cf
    gha -->|"GEMINI_API_KEY"| gha
    gha -->|"DATABRICKS_HOST/TOKEN/REPO_ID/PROD_JOB_ID"| notebooks
    notebooks --> lakebase
```

---

## 各組件要什麼、放哪

| 組件 | Secrets / Keys | 放哪 |
|------|----------------|------|
| **Cloudflare Worker**（必填 RAG） | `DATABRICKS_SERVING_URL`、`DATABRICKS_TOKEN` | `wrangler secret put` 或 `cloudflare/worker/.dev.vars` |
| **Cloudflare Worker**（選填） | `API_KEY` | 同上 |
| **Cloudflare Worker**（選填 `/meta` docs） | `DATABRICKS_WAREHOUSE_ID`、`LAKEBASE_PIPELINE_RUNS_TABLE` | 同上 |
| **Cloudflare Worker**（Lakebase） | `LAKEBASE_HOST`、`LAKEBASE_DB`、`LAKEBASE_USER`、`LAKEBASE_PASSWORD` | 同上 — `query_logs` 寫入 + Synced Table corpus 統計 |
| **Cloudflare Worker**（選填 corpus 表名） | `LAKEBASE_CASES_TABLE` | 預設 `"default".cases_meta_synced`（Synced Table）；勿用空的 `public.cases` |
| **GitHub Actions** | `GEMINI_API_KEY`、`CLOUDFLARE_API_TOKEN` | Repo → Settings → Secrets |
| **GitHub Actions**（prod pipeline） | `DATABRICKS_HOST`、`DATABRICKS_TOKEN`、`DATABRICKS_REPO_ID`、`DATABRICKS_PROD_JOB_ID` | 見 `databricks/prod_notebooks_job/README.md` |
| **Databricks Notebooks / Jobs** | Lakebase 連線；`synced_table_uc_name`；`serving_*` | Databricks secret scope `justice-compass` |
| **Cloudflare Pages** | — | 無 |
| **Demo corpus** | — | Git `data/sample/`（無 API key） |

---

## 快速對照

```
worker/.dev.vars         →  DATABRICKS_* / API_KEY / LAKEBASE_*（本機 Worker）
wrangler secret put      →  同上（已部署 Worker）
GitHub Secrets           →  GEMINI_API_KEY / CLOUDFLARE_API_TOKEN / DATABRICKS_*（prod GHA）
Databricks secret scope  →  Lakebase 帳密（notebook 用）
```
