# Lakebase — Integration Design

> This project uses Lakebase for Lake↔Base integration; it does not use AI Search (the existing Delta cosine + Model Serving setup is already enough to power RAG retrieval).

---

## The one official highlight: bidirectional Lake ↔ Base integration

**This is not "just another Postgres instance" — it's a native bridge between the Lakehouse and an operational database on the same platform.**

Sources: [Lakehouse integration](https://docs.databricks.com/aws/en/oltp/projects/lakehouse-integrations) (updated 2026-06) · [Native Lakehouse Sync announcement](https://www.databricks.com/blog/announcing-native-lakehouse-sync)

The official relationship between Lakebase and the Lakehouse:

| Direction | Official capability | Meaning |
|------|----------|------|
| **Lake → Base** | **Synced Tables** — sync a Unity Catalog–managed Delta table into Postgres | Applications get **low-latency OLTP reads** of Lakehouse data without scanning Delta directly from the edge |
| **Base → Lake** | **Lakebase Change Data Feed (CDF)** / Native Lakehouse Sync — Postgres WAL changes are written into UC Delta | Operational writes stay in Base; **analytics, audit, and lineage** appear automatically in the Lake, **with no custom CDC pipeline required** |

> "Connect Lakebase to Unity Catalog for governance, **sync Lakehouse data into Postgres** for low-latency reads, and **feed Postgres changes back to the Lakehouse**."

**Why this is what makes it "Lakebase" (Lake + Base)**: OLTP and OLAP share the same open storage / UC governance; the data flow is a **native platform property**, not a fragile ETL pipeline.

---

## Connection and authentication

This project uses a **custom Postgres ROLE with a native PASSWORD** (a fixed password), **not** OAuth / Service Principal token rotation:

| Item | This project's choice | Notes |
|------|-----------|------|
| Auth method | **Native Postgres password** | A custom role + password is created in the Lakebase SQL Editor; the password is long-lived |
| Not used | OAuth `generate_database_credential` | The official default path for external apps; tokens expire after ~60 minutes and need rotation |
| Impact | **Works directly with Cloudflare Hyperdrive** | Hyperdrive assumes a static connection string; a fixed password avoids any OAuth rotation friction |

### Secrets configuration (set up on both Databricks and Cloudflare ✅)

Both sides use the **same set** of Lakebase connection parameters (host / db / user / password), just under different key names:

| Parameter | Databricks secret scope `justice-compass` | Cloudflare Worker (`wrangler secret put`) |
|------|---------------------------------------------|-------------------------------------------|
| Host | `lakebase_host` | `LAKEBASE_HOST` |
| Database | `lakebase_db` | `LAKEBASE_DB` |
| Role (custom) | `lakebase_user` | `LAKEBASE_USER` |
| Password | `lakebase_password` | `LAKEBASE_PASSWORD` |

**Databricks usage**: Notebooks / Jobs write to `pipeline_runs` via `pipeline_log.py` (psycopg2).

**Cloudflare usage** (already configured ✅):

- **`query_logs`**: `query_log.js` inserts a row on each `/query`
- **`cases`**: `meta.js` runs a Postgres `SELECT count(*), max(ingested_at)` for `/meta` corpus stats
- **`pipeline_runs`**: Docs freshness via SQL Warehouse (see below)

**Worker `/meta` paths**:

### Role permissions (recommended)

Run this in the Lakebase SQL Editor after `lakebase_schema.sql` (see README Step 5 for the fork-it version of this same snippet):

```sql
CREATE ROLE justice_compass_app WITH LOGIN PASSWORD 'REPLACE_WITH_A_STRONG_PASSWORD';
GRANT USAGE ON SCHEMA public TO justice_compass_app;
GRANT INSERT ON public.query_logs TO justice_compass_app;
GRANT SELECT ON public.cases TO justice_compass_app;
```

Once the Synced Table exists (after running `09`), also grant read access to it:

```sql
GRANT USAGE ON SCHEMA "default" TO justice_compass_app;
GRANT SELECT ON "default".cases_meta_synced TO justice_compass_app;
```

`CONNECT` on the database is granted to `PUBLIC` by default on a fresh Lakebase project, so it's usually not needed explicitly — check your project's connection settings if the Worker can't connect.

---

## Current state of Lakebase tables

| Table | Written by | Read by | Notes |
|----|----|----|------|
| `pipeline_runs` | Notebooks / Job | Worker `/meta` docs freshness (SQL Warehouse) | ✅ |
| `query_logs` | Worker `/query` | Lakebase SQL audit | ✅; CDF→Delta blocked |
| `cases_meta_synced` (Synced Table `"default".cases_meta_synced`) | `09` Synced Tables from `cases_metadata` | Worker `/meta` `case_count` | ✅ **corpus stats read this table** |
| `public.cases` (DDL) | `lakebase_schema.sql` + optional upsert | — | Empty shell / fallback; **not** the default `/meta` source |
| `data_quality_scores` | — | — | Phase 2 backlog, schema only |

---

## Design for Justice Compass (planned, not yet implemented)

```
                    ┌── Synced Tables (Lake → Base) ──────────────┐
Delta silver/bronze │  case metadata → Lakebase.cases            │ homepage "Docs last updated"
metadata            └─────────────────────────────────────────────┘

Worker / Serving ──► Lakebase.query_logs (operational writes on the Base side)
                              │
                              └── CDF / Lakehouse Sync (Base → Lake)
                                        └── Delta audit table (compliance, demo lineage)

Delta gold_embeddings ── bundle ──► Model Serving (RAG vectors, stays in the Lake)
```

| Data | Stored where | How it demonstrates Lake+Base |
|------|------|---------------------|
| Case chunks + embeddings | Delta Gold | **Lake** — Medallion analytics layer |
| Case metadata (for UI / indexing) | Delta → **Synced Tables** → Lakebase `cases` | **Lake feeds Base**, low-latency reads at the edge |
| User Q&A audit | Lakebase `query_logs` | Real-time writes on the **Base** side |
| Q&A history analytics / governance | CDF → Delta `lb_query_logs_history` | **Base flows back to Lake** (blocked by a Free Edition architecture limit, see below ❌) |
| Pipeline run history | Lakebase `pipeline_runs` | Connects Jobs to the homepage "Model last updated" |

**Summary**: case metadata flows from Delta into Lakebase via **Synced Tables**, giving the frontend low-latency reads. Every RAG query is written to Lakebase `query_logs` for audit. The reverse direction, **Lakebase CDF** (Base flowing back to Lake), has been configured and the setup steps themselves are correct, but on Free Edition the catalog only has default storage, and a CDF destination requires a custom cloud storage location — so it is not architecturally supported (see "CDF verification status" below for details).

---

## Implementation plan (in progress)

| # | Item | Status | Notes |
|---|------|------|------|
| 1 | Create a Free Edition Lakebase project + UC registration | ✅ | 1 project / account |
| 2 | Run `lakebase_schema.sql` | ✅ | Four tables (including the `serving` layer) |
| 3 | **Synced Tables**: Delta `cases_metadata` → Lakebase | ✅ | **`09`** + fallback `cases` upsert; Synced Table UI is optional |
| 4 | Worker writes to `query_logs` | ✅ | **`query_log.js`** + `LAKEBASE_*` secrets verified |
| 5 | **CDF**: `query_logs` → Delta `lb_query_logs_history` | ❌ | UI configured; **the Delta table never appears** — confirmed to be a Free Edition storage architecture limit, not a bug, see below |
| 6 | Job writes to `pipeline_runs`; homepage freshness | ✅ | **`07` + 01–03/05 + UC + Worker `/meta` + Pages UI** |

### Homepage freshness display (Phase 3 UI requirement)

The homepage (`cloudflare/pages/index.html`) needs to display:

| Field | Data source |
|------|----------|
| **Corpus count / last synced** | Synced Table **`"default".cases_meta_synced`** (direct Postgres connection; overridable via `LAKEBASE_CASES_TABLE`) |
| **Docs last updated** | `pipeline_runs` Gold success (SQL Warehouse) |
| **Model last updated** | MLflow registered model |

The Worker's **`GET /meta`** already implements:

- **Corpus**: `case_count`, `cases_last_updated` — Synced Table `"default".cases_meta_synced` (requires `LAKEBASE_*`; **not** the DDL `public.cases`)
- **Model last updated**: MLflow registered model API
- **Docs last updated**: SQL warehouse query against `pipeline_runs` (requires `DATABRICKS_WAREHOUSE_ID`, `LAKEBASE_PIPELINE_RUNS_TABLE`)

The Pages homepage calls `/meta` on load to display corpus + docs + model timestamps.

> **Citations do not read from `cases`** — Q&A citations come from Gold vector retrieval; the Synced Table is only used for the corpus catalog count.
>
> **"Corpus: 0 cases"**: this happens if the Worker is pointed at the empty `public.cases` (DDL) or an old table named `cases`; confirm the Worker is querying the Synced Table `"default".cases_meta_synced`.

### Worker `query_logs` (implemented ✅, pending deploy verification)

After each successful `GET/POST /query`, `ctx.waitUntil` asynchronously `INSERT`s into Lakebase `query_logs`:

| Column | Source |
|------|------|
| `question` | The user's query |
| `answer_preview` | First 500 characters of the answer |
| `citation_count` | Length of the citations array |
| `mock_mode` | Whether the mock fallback was used |
| `latency_ms` | Worker end-to-end latency in milliseconds |

Implementation: `cloudflare/worker/src/query_log.js` (`postgres` + `LAKEBASE_*` secrets).
Verification: after `curl .../query?q=...`, check Lakebase with `SELECT * FROM query_logs ORDER BY created_at DESC LIMIT 5;`

---

## CDF verification status (Base → Lake) ❌ Free Edition architecture limit

**Date**: 2026-07-06
**Setup completed**: `ALTER TABLE query_logs REPLICA IDENTITY FULL;` plus the Lakebase UI **Change Data Feed** was enabled (destination catalog e.g. `justice_compass_lakebase.default`).

**Problem**: after running `10_lakebase_cdf_setup`, **`lb_query_logs_history` never appears** in UC; there is no destination Delta table under `wal2delta.tables` / the catalog, even though `query_logs` already has rows written by the Worker.

**Conclusion** (updated 2026-07-10, confirmed on the [Databricks Community](https://community.databricks.com/t5/data-engineering/lakebase-cdf-destination-delta-table-not-created-after/m-p/162161#M55045)): **this is a known limitation of Free Edition's storage architecture, not a bug**. A Lakebase CDF destination must be a Unity Catalog **managed Delta table**, and the official docs list "a catalog backed by default storage" as an **unsupported CDF destination**. Free Edition workspaces always use default storage (the catalog's storage path contains `unitystorage`), so the destination Delta table **cannot architecturally be created** on Free Edition — there is no platform fix to wait for. To verify that CDF actually works, you would need a paid workspace with a catalog backed by a **custom cloud storage location** (an external location). Git: commit `a02f5f5`'s message records the same symptom.

**MVP impact**:

| Capability | Status |
|------|------|
| Q&A audit writes to Lakebase `query_logs` | ✅ works |
| Delta audit table `lb_query_logs_history` | ❌ Free Edition architecture limit, not a bug |
| Audit demo | Query `query_logs` directly in the Lakebase SQL Editor (see workaround below) |

**Workaround (for demos)**:

```sql
-- Lakebase SQL Editor
SELECT question, mock_mode, latency_ms, created_at
FROM query_logs ORDER BY created_at DESC LIMIT 10;
```

**If you switch to a paid workspace (catalog backed by a custom cloud storage location)**: Pull → run `10` → confirm `justice_compass_lakebase.default.lb_query_logs_history` has a `_pg_change_type` column.

---

## References

- [Connection strings (native password vs OAuth)](https://docs.databricks.com/aws/en/oltp/projects/connection-strings)
- [Connect external app (OAuth path — not used in this project)](https://docs.databricks.com/aws/en/oltp/projects/external-apps-connect)
- [Cloudflare Hyperdrive + Postgres](https://developers.cloudflare.com/hyperdrive/) (a fixed password can be configured directly)
- [Lakehouse integration](https://docs.databricks.com/aws/en/oltp/projects/lakehouse-integrations)
- [Lakebase Change Data Feed](https://docs.databricks.com/aws/en/oltp/projects/lakebase-cdf) (Public Preview)
- [Databricks Community: Lakebase CDF destination Delta table not created (Free Edition)](https://community.databricks.com/t5/data-engineering/lakebase-cdf-destination-delta-table-not-created-after/m-p/162161#M55045) (confirms this is a default-storage limitation, not a bug)
- [Announcing Native Lakehouse Sync](https://www.databricks.com/blog/announcing-native-lakehouse-sync)
- [Lakebase Postgres overview](https://docs.databricks.com/aws/en/oltp/projects/)
- [Free Edition limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
