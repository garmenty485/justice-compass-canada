"""Refresh Delta cases_metadata without replacing table identity (Synced Table safe)."""

from __future__ import annotations

from typing import Any

UC_CATALOG = "workspace"
UC_SCHEMA = "default"
BRONZE_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.bronze_cases"
CASES_METADATA_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.cases_metadata"

_CASES_METADATA_SELECT = """
SELECT
    case_id,
    citation,
    title,
    court,
    CAST(decision_date AS DATE) AS decision_date,
    canlii_url,
    topics,
    CAST(ingested_at AS TIMESTAMP) AS ingested_at
FROM {bronze_table}
"""


def _select_sql(bronze_table: str) -> str:
    return _CASES_METADATA_SELECT.format(bronze_table=bronze_table)


def ensure_cdf_enabled(spark: Any, cases_metadata_table: str) -> None:
    spark.sql(
        f"""
        ALTER TABLE {cases_metadata_table}
        SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
        """
    )


def refresh_cases_metadata(
    spark: Any,
    *,
    bronze_table: str = BRONZE_TABLE,
    cases_metadata_table: str = CASES_METADATA_TABLE,
) -> int:
    """
    Upsert cases_metadata while preserving Delta table ID.

    First run: CREATE TABLE ... USING DELTA AS SELECT.
    Subsequent runs: INSERT OVERWRITE (keeps Synced Table checkpoint valid).
    Always enables CDF for Triggered sync.
    """
    bronze_count = spark.table(bronze_table).count()
    if bronze_count == 0:
        raise RuntimeError(f"{bronze_table} is empty. Run bronze ingest first.")

    select_sql = _select_sql(bronze_table)
    if spark.catalog.tableExists(cases_metadata_table):
        spark.sql(
            f"""
            INSERT OVERWRITE TABLE {cases_metadata_table}
            {select_sql}
            """
        )
    else:
        spark.sql(
            f"""
            CREATE TABLE {cases_metadata_table}
            USING DELTA
            AS
            {select_sql}
            """
        )

    ensure_cdf_enabled(spark, cases_metadata_table)
    return spark.table(cases_metadata_table).count()
