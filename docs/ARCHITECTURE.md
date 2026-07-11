# Architecture

See [README.md](../README.md) for the system architecture diagram.

## Request flow

1. User submits question on **Cloudflare Pages** (vanilla JS)
2. **Worker** validates request, optional auth, forwards to Databricks
3. **RAG endpoint** retrieves Gold-layer chunks, generates answer + citations
4. Response rendered with citation links and legal disclaimer

**Citations**: Live RAG returns top-k chunks from `gold_embeddings` (not Lakebase). Mock mode uses a single synthetic citation in the Worker.

**Corpus**: Four **synthetic** BC liquor-licensing JSON files in `data/sample/` (not live CanLII ingestion).

## Data layers (Medallion)

MVP tables in **default catalog** (Free Edition, `workspace.default`) — no separate UC schema layer is provisioned.

| Layer | Table | Content | Source |
|-------|-------|---------|--------|
| Bronze | `bronze_cases` | Raw case JSON fields | Git folder `data/sample/` via `01` |
| Silver | `silver_chunks` | Cleaned text chunks | `02` |
| Gold | `gold_embeddings` | Vectors + citation metadata | `03` |

**Not used on Free Edition:** manual `/FileStore/justice-compass/...` upload; public DBFS staging (`dbutils.fs` to `/tmp/` on DBFS).

## Lakebase (Lake ↔ Base) — **required**

Lakebase is **not** a standalone Postgres sidecar. Official model: [Lakehouse integration](https://docs.databricks.com/aws/en/oltp/projects/lakehouse-integrations).

| Direction | Mechanism | Justice Compass use |
|-----------|-----------|---------------------|
| **Lake → Base** | **Synced Tables** (UC Delta → Postgres) | Case metadata → Lakebase `cases`; **corpus count** on homepage via `/meta` |
| **Base → Lake** | **Lakebase CDF** / Native Lakehouse Sync (Postgres WAL → Delta) | `query_logs` audit trail in open lake format without custom CDC |

Tables (DDL): `databricks/sql/lakebase_schema.sql` · Plan: [`docs/LAKEBASE.md`](LAKEBASE.md)

**Auth**: custom Postgres ROLE + native PASSWORD (not OAuth). Secrets in Databricks `justice-compass` scope and Cloudflare Worker (`LAKEBASE_*`); enables future Hyperdrive direct Postgres from edge.

## Free Edition path (2026-06)

Databricks Free Edition **includes** Lakebase and Jobs with quotas. See [official limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations).

| Component | Free Edition | MVP default |
|-----------|--------------|-------------|
| Medallion pipeline | ✅ notebooks 01→03 | **Job** `justice-compass-medallion` (see [`docs/JOBS.md`](JOBS.md)) |
| Embeddings | ✅ Delta `gold_embeddings` | Always |
| Vector retrieval | Delta cosine | **`04` notebook + Serving pyfunc** — **no AI Search** |
| Metadata / logs | ✅ Lakebase (1 project) | **Required** — schema ready |
| Orchestration | ✅ Jobs (5 concurrent tasks) | **01→03 now**; **05/06 auto later** (zero-downtime, [`docs/JOBS.md`](JOBS.md)) |
| Serving deploy | ✅ Model Serving | **`05` manual now** → future Job task after gold |
| Homepage freshness | Worker `/meta` | **Model + Docs + Corpus** (`case_count` from Lakebase `cases`) |

**Current architecture** (Phase 2 live; Lake+Base planned):

```
Delta cases_metadata ──Synced Tables──► Lakebase "default".cases ──► /meta case_count + Pages corpus line
Worker query ──► Lakebase query_logs ──CDF──► Delta audit (blocked)
Delta gold_embeddings ──bundle──► Serving ──► Worker ──► Pages
Job 01→02→03 (now) ──► [future 05→06 zero-downtime deploy] ──► Model last updated
```

## Security

- Databricks tokens only in Worker secrets (never in Pages)
- Optional `API_KEY` on Worker
- CORS limited in production (update Worker headers)
