"""Databricks secret scope helpers for justice-compass notebooks."""

from __future__ import annotations

from typing import Any

SCOPE = "justice-compass"
DEFAULT_SYNCED_TABLE_UC_NAME = "workspace.default.cases_meta_synced"


def secret_or_default(dbutils: Any, key: str, default: str) -> str:
    """Read a secret from scope `justice-compass`, falling back to default."""
    try:
        value = dbutils.secrets.get(scope=SCOPE, key=key).strip()
        if value:
            return value
    except Exception:
        pass
    return default


def resolve_synced_table_uc_name(
    dbutils: Any,
    widget_value: str | None = None,
    *,
    default: str = DEFAULT_SYNCED_TABLE_UC_NAME,
) -> str:
    """
    Resolve Synced Table UC name: secret > widget > default.
    """
    secret_value = secret_or_default(dbutils, "synced_table_uc_name", "")
    if secret_value:
        return secret_value
    if widget_value and widget_value.strip():
        return widget_value.strip()
    return default
