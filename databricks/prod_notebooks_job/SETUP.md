# Prod — Synced Table one-time setup

> Prod Job **`09_sync_cases_prod`** refreshes `cases_metadata` (INSERT OVERWRITE) and **triggers** an existing Synced Table. Create the Synced Table once in the UI.

## Prerequisites

- Run prod `01` at least once so `workspace.default.bronze_cases` exists.
- Lakebase project + branch online.

## Steps (Catalog UI)

1. Open **`workspace.default.cases_metadata`** (created by prod `09` or dev `09` §1).
2. **Create** → **Synced table**.
3. Database: **Lakebase Serverless** → your project / branch / database.
4. Sync mode: **Triggered** (CDF enabled idempotently by prod `09` / dev `09`).
5. Primary key: **`case_id`**.
6. Suggested synced table name: **`cases_meta_synced`**.
7. Wait until status **Online**.
8. Note the three-part UC name: **`workspace.default.cases_meta_synced`**.

## Configure prod 09

Set Databricks secret scope `justice-compass` → **`synced_table_uc_name`** = `workspace.default.cases_meta_synced`.

Fallback order: secret → Job widget / `base_parameters` → notebook default.

Prod Job `sync_cases` task already passes `SYNCED_TABLE_UC_NAME` via `prod_pipeline_job.py`.

## Verify

```sql
SELECT count(*) FROM "default".cases_meta_synced;
```

Worker `/meta` `case_count` should match after the next prod Job run.

Docs: https://docs.databricks.com/aws/en/oltp/projects/sync-tables
