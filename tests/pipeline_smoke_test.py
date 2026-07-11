#!/usr/bin/env python3
"""Smoke tests for sample data and notebook skeletons."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "data" / "sample"
NOTEBOOKS = ROOT / "databricks" / "notebooks"
REQUIRED_FIELDS = {"caseId", "title", "citation", "fullText", "url"}


def test_sample_cases() -> None:
    files = list(SAMPLE_DIR.glob("*.json"))
    assert files, f"No sample files in {SAMPLE_DIR}"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = REQUIRED_FIELDS - data.keys()
        assert not missing, f"{path.name} missing fields: {missing}"
        assert len(data["fullText"]) > 50, f"{path.name} fullText too short"
        assert data.get("_note"), f"{path.name} missing _note synthetic marker"
    print(f"OK: {len(files)} sample cases validated")


def test_notebooks_exist() -> None:
    expected = [
        "01_bronze_ingest.py",
        "02_silver_transform.py",
        "03_gold_embed.py",
        "04_rag_serving.py",
        "05_deploy_serving.py",
        "06_create_serving_endpoint_api.py",
        "07_lakebase_setup.py",
    ]
    for name in expected:
        path = NOTEBOOKS / name
        assert path.exists(), f"Missing notebook: {name}"
    print(f"OK: {len(expected)} notebook skeletons present")

    serving = ROOT / "databricks" / "serving" / "justice_compass_rag.py"
    assert serving.exists(), "Missing serving/justice_compass_rag.py"
    api_helper = ROOT / "databricks" / "serving" / "create_endpoint_api.py"
    assert api_helper.exists(), "Missing serving/create_endpoint_api.py"
    lakebase = ROOT / "databricks" / "lakebase" / "pipeline_log.py"
    assert lakebase.exists(), "Missing lakebase/pipeline_log.py"
    print("OK: serving + lakebase modules present")


if __name__ == "__main__":
    try:
        test_sample_cases()
        test_notebooks_exist()
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
