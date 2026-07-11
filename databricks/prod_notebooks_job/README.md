# Prod pipeline — `databricks/prod_notebooks_job/`

Scheduled production flow: **GitHub Actions** seeds a testcase → push → Databricks Pull → **Job run-now**.

All prod notebooks live here (separate from dev `databricks/notebooks/`).

## Flow

```
GHA (every 2h)                    Databricks Job (no schedule)
─────────────────                 ─────────────────────────────
seed_test_case.py                 01 bronze_ingest
  → commit push main                 → 02 silver_transform
  → Repos API Pull                  → 03 gold_embed
  → jobs/run-now                    → 05 deploy_serving
                                    → 09 sync_cases_prod
```

## One-time setup

1. **Synced Table** — follow [`SETUP.md`](SETUP.md); UC name `workspace.default.cases_meta_synced`.
2. **Databricks secret** — scope `justice-compass` → `synced_table_uc_name` = `workspace.default.cases_meta_synced`.
3. **Create Job** — Git Pull → run **`create_prod_pipeline_job`** → note `job_id`.
4. **GitHub Secrets** (repo Settings):

| Secret | Value |
|--------|--------|
| `DATABRICKS_HOST` | `https://<workspace>.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | PAT (Repos + Jobs) |
| `DATABRICKS_REPO_ID` | Git folder id (Repos UI or API) |
| `DATABRICKS_PROD_JOB_ID` | From step 2 |

5. **Test** — Actions → **Prod seed and pipeline** → **Run workflow** (waits for Databricks Job SUCCESS).

## Manual validation

- `create_prod_pipeline_job`: set `RUN_NOW = True` after Pull.
- Workflows → `justice-compass-prod-pipeline` → Runs.

## vs dev `notebooks/`

| | Dev | Prod |
|---|-----|------|
| Folder | `databricks/notebooks/` | `databricks/prod_notebooks_job/` |
| Job | `justice-compass-medallion` (01→03) | `justice-compass-prod-pipeline` (01→05→09) |
| Trigger | Manual | GHA every 2h |
| Seed | Manual JSON in Git | GHA `scripts/seed_test_case.py` |
| 09 | Full setup + fallback upsert | Metadata + Synced Table trigger only |

## Risks

- **05 every 2h** — Serving quota / cold start on Free Edition.
- **01 overwrite** — full re-ingest; slows as `testcase*` count grows.
- **09** — fails loud if sync pipeline errors; uses INSERT OVERWRITE (not CREATE OR REPLACE).
