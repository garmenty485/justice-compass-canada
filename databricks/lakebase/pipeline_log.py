"""
Write Medallion / serving run metadata to Lakebase pipeline_runs.

Auth: custom Postgres ROLE + native PASSWORD (not OAuth). Same credentials
in Databricks secret scope and Cloudflare Worker — see docs/LAKEBASE.md.

Optional: configure Databricks secret scope `justice-compass` with:
  lakebase_host, lakebase_db, lakebase_user, lakebase_password
Or set env vars LAKEBASE_HOST, LAKEBASE_DB, LAKEBASE_USER, LAKEBASE_PASSWORD.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any


def _conn_params(dbutils: Any | None = None) -> dict[str, str] | None:
    keys = ("lakebase_host", "lakebase_db", "lakebase_user", "lakebase_password")
    values: dict[str, str] = {}

    if dbutils is not None:
        try:
            for key in keys:
                values[key] = dbutils.secrets.get(scope="justice-compass", key=key)
        except Exception:
            values = {}

    env_map = {
        "lakebase_host": "LAKEBASE_HOST",
        "lakebase_db": "LAKEBASE_DB",
        "lakebase_user": "LAKEBASE_USER",
        "lakebase_password": "LAKEBASE_PASSWORD",
    }
    for key, env_key in env_map.items():
        if not values.get(key):
            val = os.environ.get(env_key, "").strip()
            if val:
                values[key] = val

    if not all(values.get(k) for k in keys):
        return None
    return values


def log_pipeline_run(
    layer: str,
    status: str,
    *,
    row_count: int | None = None,
    error_message: str | None = None,
    run_id: str | None = None,
    dbutils: Any | None = None,
) -> str | None:
    """
    Insert one row into Lakebase pipeline_runs. Returns run_id or None if skipped.
    """
    if layer not in ("bronze", "silver", "gold", "serving"):
        raise ValueError(f"Invalid layer: {layer}")

    params = _conn_params(dbutils)
    if not params:
        print("Lakebase pipeline_log skipped (no connection secrets).")
        return None

    run_id = run_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    try:
        import psycopg2
    except ImportError:
        print("Lakebase pipeline_log skipped (install psycopg2-binary in notebook).")
        return None

    conn = psycopg2.connect(
        host=params["lakebase_host"],
        dbname=params["lakebase_db"],
        user=params["lakebase_user"],
        password=params["lakebase_password"],
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (run_id, layer, status, row_count, started_at, finished_at, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    row_count = EXCLUDED.row_count,
                    finished_at = EXCLUDED.finished_at,
                    error_message = EXCLUDED.error_message
                """,
                (
                    run_id,
                    layer,
                    status,
                    row_count,
                    now,
                    now if status in ("success", "failed") else None,
                    error_message,
                ),
            )
        conn.commit()
        print(f"Lakebase pipeline_runs: layer={layer} status={status} run_id={run_id}")
        return run_id
    finally:
        conn.close()
