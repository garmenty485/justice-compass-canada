"""Sync case metadata from Delta to Lakebase cases (Lake → Base fallback)."""

from __future__ import annotations

from typing import Any

from pipeline_log import _conn_params


def upsert_cases_from_spark(
    spark: Any,
    table_name: str,
    *,
    dbutils: Any | None = None,
) -> int:
    """
    Upsert rows from a Delta/Spark table into Lakebase public.cases.
    Column mapping: case_id, citation, title, court, decision_date, canlii_url, topics, ingested_at.
    """
    params = _conn_params(dbutils)
    if not params:
        print("Lakebase sync_cases skipped (no connection secrets).")
        return 0

    try:
        import psycopg2
        from psycopg2.extras import execute_batch
    except ImportError:
        print("Lakebase sync_cases skipped (install psycopg2-binary).")
        return 0

    df = spark.table(table_name).select(
        "case_id",
        "citation",
        "title",
        "court",
        "decision_date",
        "canlii_url",
        "topics",
        "ingested_at",
    )
    rows = df.collect()
    if not rows:
        print(f"No rows in {table_name}")
        return 0

    payload = [
        (
            r.case_id,
            r.citation,
            r.title,
            r.court,
            r.decision_date,
            r.canlii_url,
            list(r.topics) if r.topics is not None else None,
            r.ingested_at,
        )
        for r in rows
    ]

    conn = psycopg2.connect(
        host=params["lakebase_host"],
        dbname=params["lakebase_db"],
        user=params["lakebase_user"],
        password=params["lakebase_password"],
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            execute_batch(
                cur,
                """
                INSERT INTO cases
                    (case_id, citation, title, court, decision_date, canlii_url, topics, ingested_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (case_id) DO UPDATE SET
                    citation = EXCLUDED.citation,
                    title = EXCLUDED.title,
                    court = EXCLUDED.court,
                    decision_date = EXCLUDED.decision_date,
                    canlii_url = EXCLUDED.canlii_url,
                    topics = EXCLUDED.topics,
                    ingested_at = EXCLUDED.ingested_at
                """,
                payload,
                page_size=100,
            )
        conn.commit()
        print(f"Lakebase cases upserted: {len(payload)} rows from {table_name}")
        return len(payload)
    finally:
        conn.close()
