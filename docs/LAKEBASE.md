# Lakebase — 專案整合計畫

> **決策（2026-07-05）**：Lakebase **必做**；AI Search **不做**（現有 Delta cosine + Model Serving 已足 MVP）。

---

## 官方亮點（一個）：Lake ↔ Base 雙向整合

**不是「多一個 Postgres」——是 Lakehouse 與 Operational DB 在同一平台上的原生銜接。**

來源：[Lakehouse integration](https://docs.databricks.com/aws/en/oltp/projects/lakehouse-integrations)（2026-06 更新）· [Native Lakehouse Sync 公告](https://www.databricks.com/blog/announcing-native-lakehouse-sync)

官方定義 Lakebase 與 Lakehouse 的關係：

| 方向 | 官方能力 | 意義 |
|------|----------|------|
| **Lake → Base** | **Synced Tables** — 把 Unity Catalog 管理的 Delta 表同步進 Postgres | 應用程式用**低延遲 OLTP 讀取** Lakehouse 資料，不必從 Edge 直掃 Delta |
| **Base → Lake** | **Lakebase Change Data Feed (CDF)** / Native Lakehouse Sync — Postgres WAL 變更寫入 UC Delta | 營運寫入留在 Base；**分析、稽核、血緣**在 Lake 自動有，**無需自建 CDC pipeline** |

> 「Connect Lakebase to Unity Catalog for governance, **sync Lakehouse data into Postgres** for low-latency reads, and **feed Postgres changes back to the Lakehouse**.」

**為什麼這才像 Lakebase（Lake + Base）**：OLTP 與 OLAP 共用同一套 open storage / UC 治理；資料流是**平台原生屬性**，不是 fragile ETL。

---

## 連線與認證（已決策 ✅）

> **決策（2026-07-06）**：使用 **自訂 Postgres ROLE + native PASSWORD**（固定密碼），**不用** OAuth / Service Principal token rotation。

| 項目 | 本專案選擇 | 說明 |
|------|-----------|------|
| 認證方式 | **Native Postgres password** | Lakebase SQL Editor 建立自訂 role + password；密碼長期有效 |
| 未採用 | OAuth `generate_database_credential` | 官方外部 app 預設路徑；token ~60 分鐘過期，需輪替 |
| 影響 | **Cloudflare Hyperdrive 可直接使用** | Hyperdrive 假設 connection string 靜態；固定 password 無 OAuth 輪替障礙 |

### Secrets 配置（Databricks + Cloudflare 皆已設定 ✅）

兩邊使用**同一組** Lakebase 連線參數（host / db / user / password），僅 key 命名不同：

| 參數 | Databricks secret scope `justice-compass` | Cloudflare Worker (`wrangler secret put`) |
|------|---------------------------------------------|-------------------------------------------|
| Host | `lakebase_host` | `LAKEBASE_HOST` |
| Database | `lakebase_db` | `LAKEBASE_DB` |
| Role（自訂） | `lakebase_user` | `LAKEBASE_USER` |
| Password | `lakebase_password` | `LAKEBASE_PASSWORD` |

**Databricks 用途**：Notebooks / Jobs 經 `pipeline_log.py`（psycopg2）寫入 `pipeline_runs`。

**Cloudflare 用途**（已設定 ✅）：

- **`query_logs`**：`query_log.js` INSERT on each `/query`
- **`cases`**：`meta.js` Postgres `SELECT count(*), max(ingested_at)` for `/meta` corpus stats
- **`pipeline_runs`**：Docs freshness via SQL Warehouse（見下）

**Worker `/meta` paths**：

### Role 權限（建議）

自訂 role 至少需：

- `CONNECT` on database
- `USAGE` on schema（含表所在 schema）
- `INSERT` on `query_logs`（Worker audit ✅）
- `SELECT` on `cases`（Worker `/meta` corpus stats ✅）

---

## Lakebase 表使用現況

| 表 | 寫 | 讀 | 備註 |
|----|----|----|------|
| `pipeline_runs` | Notebooks / Job | Worker `/meta` docs freshness（SQL Warehouse） | ✅ |
| `query_logs` | Worker `/query` | Lakebase SQL audit | ✅；CDF→Delta blocked |
| `cases_meta_synced`（Synced Table `"default".cases_meta_synced`） | `09` Synced Tables from `cases_metadata` | Worker `/meta` `case_count` | ✅ **corpus 讀這張** |
| `public.cases`（DDL） | `lakebase_schema.sql` + optional upsert | — | 空殼 / fallback；**不是** `/meta` 預設來源 |
| `data_quality_scores` | — | — | P2，schema only |

---

## 在 Justice Compass 的設計（計畫，尚未實作）

```
                    ┌── Synced Tables (Lake → Base) ──────────────┐
Delta silver/bronze │  case metadata → Lakebase.cases            │ 首頁「Docs last updated」
metadata            └─────────────────────────────────────────────┘

Worker / Serving ──► Lakebase.query_logs (Base 營運寫入)
                              │
                              └── CDF / Lakehouse Sync (Base → Lake)
                                        └── Delta audit 表（合規、Demo 血緣）

Delta gold_embeddings ── bundle ──► Model Serving（RAG 向量，維持在 Lake）
```

| 資料 | 存哪 | 怎麼體現 Lake+Base |
|------|------|---------------------|
| 判例 chunk + embedding | Delta Gold | **Lake** — Medallion 分析層 |
| 判例 metadata（給 UI / 索引） | Delta → **Synced Tables** → Lakebase `cases` | **Lake 餵 Base**，Edge 低延遲讀 |
| 使用者問答 audit | Lakebase `query_logs` | **Base** 即時寫入 |
| 問答歷史分析 / 治理 | CDF → Delta `lb_query_logs_history` | **Base 回流 Lake**，免自建 CDC |
| Pipeline 執行紀錄 | Lakebase `pipeline_runs` | 銜接 Job 與首頁「Model last updated」 |

**Demo 展示句（面試用）**：「判例 metadata 從 Delta **Synced Tables** 進 Lakebase 給前端低延遲讀；每次 RAG 查詢寫入 Lakebase `query_logs`，再經 **Lakebase CDF** 自動進 Delta 做稽核——不是把 Postgres 當外部 DB 硬接，而是 Lake 與 Base 在同一 UC 治理下雙向流動。」

---

## 實作計畫（待開發）

| # | 項目 | 狀態 | 說明 |
|---|------|------|------|
| 1 | 建立 Free Edition Lakebase project + UC 註冊 | ✅ | 1 project / account |
| 2 | 執行 `lakebase_schema.sql` | ✅ | 四張表（含 `serving` layer） |
| 3 | **Synced Tables**：Delta `cases_metadata` → Lakebase | ✅ | **`09`** + fallback `cases` upsert；Synced Table UI 可選 |
| 4 | Worker 寫 `query_logs` | ✅ | **`query_log.js`** + `LAKEBASE_*` secrets 驗收 |
| 5 | **CDF**：`query_logs` → Delta `lb_query_logs_history` | ⚠️ | UI 已設定；**Delta 表未出現**（Free Edition / preview，見下方） |
| 6 | Job 寫 `pipeline_runs`；首頁 freshness | ✅ | **`07` + 01–03/05 + UC + Worker `/meta` + Pages UI** |

### 首頁 freshness 顯示（Phase 3 UI 需求）

首頁（`cloudflare/pages/index.html`）需顯示：

| 欄位 | 資料來源 |
|------|----------|
| **Corpus count / last synced** | Synced Table **`"default".cases_meta_synced`**（Postgres 直連；可覆寫 `LAKEBASE_CASES_TABLE`） |
| **Docs last updated** | `pipeline_runs` Gold success（SQL Warehouse） |
| **Model last updated** | MLflow registered model |

Worker **`GET /meta`** 已實作：

- **Corpus**：`case_count`, `cases_last_updated` — Synced Table `"default".cases_meta_synced`（需 `LAKEBASE_*`；**不是** DDL `public.cases`）
- **Model last updated**：MLflow registered model API
- **Docs last updated**：SQL warehouse 查 `pipeline_runs`（需 `DATABRICKS_WAREHOUSE_ID`、`LAKEBASE_PIPELINE_RUNS_TABLE`）

Pages 首頁載入時呼叫 `/meta` 顯示 corpus + docs + model 時間。

> **Citations 不讀 `cases`** — 問答引用來自 Gold 向量檢索；Synced Table 僅 corpus catalog。
>
> **Corpus: 0 cases**：若連到空的 `public.cases`（DDL）或舊表名 `cases` 會發生；確認 Worker 查的是 Synced Table `"default".cases_meta_synced`。

### Worker `query_logs`（已實作 ✅ 待 deploy 驗收）

每次 `GET/POST /query` 成功後，`ctx.waitUntil` 非同步 `INSERT` 至 Lakebase `query_logs`：

| 欄位 | 來源 |
|------|------|
| `question` | 使用者 query |
| `answer_preview` | 回答前 500 字 |
| `citation_count` | citations 陣列長度 |
| `mock_mode` | 是否 mock fallback |
| `latency_ms` | Worker 端到端毫秒 |

實作：`cloudflare/worker/src/query_log.js`（`postgres` + `LAKEBASE_*` secrets）。  
驗證：`curl .../query?q=...` 後查 Lakebase `SELECT * FROM query_logs ORDER BY created_at DESC LIMIT 5;`

---

## CDF 驗收狀態（Base → Lake）⚠️

**日期**：2026-07-06  
**設定完成**：`ALTER TABLE query_logs REPLICA IDENTITY FULL;` + Lakebase UI **Change Data Feed** 已啟動（destination catalog 如 `justice_compass_lakebase.default`）。

**問題**：執行 `10_lakebase_cdf_setup` 時 **`lb_query_logs_history` 未在 UC 出現**；`wal2delta.tables` / Catalog 無 destination Delta 表，儘管 `query_logs` 已有 Worker 寫入。

**判定**：Lakebase CDF 為 **Public Preview**；Free Edition 上可能為平台問題（待向 Databricks 回報）。Git：`a02f5f5` commit message 記錄相同現象。

**MVP 影響**：

| 能力 | 狀態 |
|------|------|
| 問答 audit 寫入 Lakebase `query_logs` | ✅ 可用 |
| Delta 稽核表 `lb_query_logs_history` | ❌  blocked |
| Demo 敘事 | 仍可在 Lakebase SQL 展示 audit；CDF→Delta 改口徑為「已配置、preview 待平台修復」 |

**Workaround（Demo）**：

```sql
-- Lakebase SQL Editor
SELECT question, mock_mode, latency_ms, created_at
FROM query_logs ORDER BY created_at DESC LIMIT 10;
```

**若 CDF 修復後重驗**：Pull → 跑 `10` → 確認 `justice_compass_lakebase.default.lb_query_logs_history` 有 `_pg_change_type` 列。

---

## 參考連結

- [Connection strings（native password vs OAuth）](https://docs.databricks.com/aws/en/oltp/projects/connection-strings)
- [Connect external app（OAuth 路徑 — 本專案未採用）](https://docs.databricks.com/aws/en/oltp/projects/external-apps-connect)
- [Cloudflare Hyperdrive + Postgres](https://developers.cloudflare.com/hyperdrive/)（固定 password 可直接配置）
- [Lakehouse integration](https://docs.databricks.com/aws/en/oltp/projects/lakehouse-integrations)
- [Lakebase Change Data Feed](https://docs.databricks.com/aws/en/oltp/projects/lakebase-cdf)（Public Preview）
- [Announcing Native Lakehouse Sync](https://www.databricks.com/blog/announcing-native-lakehouse-sync)
- [Lakebase Postgres 概覽](https://docs.databricks.com/aws/en/oltp/projects/)
- [Free Edition 配額](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
