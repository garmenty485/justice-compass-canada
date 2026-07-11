#!/usr/bin/env python3
"""Create the next synthetic testcaseNNNN.json under data/sample/."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
TESTCASE_PATTERN = re.compile(r"^testcase(\d{4})\.json$", re.IGNORECASE)


def next_serial() -> int:
    max_n = 0
    for path in SAMPLE_DIR.glob("testcase*.json"):
        match = TESTCASE_PATTERN.match(path.name)
        if match:
            max_n = max(max_n, int(match.group(1)))
    return max_n + 1


def build_document(serial: int) -> dict:
    case_id = f"testcase{serial:04d}"
    return {
        "caseId": {"databaseId": "demo", "caseId": case_id},
        "title": f"Test Case {serial:04d}",
        "citation": f"TEST {serial:04d}",
        "decisionDate": date.today().isoformat(),
        "url": f"https://justice-compass.demo/cases/{case_id}",
        "keywords": ["test", "synthetic"],
        "fullText": f"這是測試範例{serial}",
        "jurisdiction": "British Columbia",
        "court": "Demo Court",
        "topics": ["prod seed"],
        "_note": "Synthetic prod seed — not a real decision.",
    }


def main() -> int:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    serial = next_serial()
    case_id = f"testcase{serial:04d}"
    out_path = SAMPLE_DIR / f"{case_id}.json"
    if out_path.exists():
        print(f"error: {out_path} already exists", file=sys.stderr)
        return 1

    doc = build_document(serial)
    out_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(case_id)
    print(f"wrote {out_path.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
