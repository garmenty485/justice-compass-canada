#!/usr/bin/env python3
"""Post a Gemini-based PR review comment. Used by .github/workflows/ai-pr-review.yml"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

MAX_DIFF_CHARS = 48_000
DEFAULT_MODEL = "gemini-2.0-flash"


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("GEMINI_API_KEY not set — skip AI review.", file=sys.stderr)
        return 0

    diff_path = os.environ.get("DIFF_PATH", "pr.diff")
    prompt_path = os.environ.get("PROMPT_PATH", ".github/ai/pr-review-prompt.md")
    model = os.environ.get("AI_REVIEW_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    try:
        with open(diff_path, encoding="utf-8", errors="replace") as f:
            diff = f.read(MAX_DIFF_CHARS + 1)
    except OSError as exc:
        print(f"Cannot read diff: {exc}", file=sys.stderr)
        return 1

    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n... [diff truncated] ..."

    try:
        with open(prompt_path, encoding="utf-8") as f:
            system_prompt = f.read()
    except OSError as exc:
        print(f"Cannot read prompt: {exc}", file=sys.stderr)
        return 1

    pr_title = os.environ.get("PR_TITLE", "")
    pr_body = os.environ.get("PR_BODY", "")[:4000]
    user_content = (
        f"Pull request title: {pr_title}\n\n"
        f"Pull request description:\n{pr_body or '(empty)'}\n\n"
        f"Unified diff:\n```diff\n{diff}\n```"
    )

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        print(f"Gemini API error {exc.code}: {detail}", file=sys.stderr)
        return 1

    try:
        review_text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        print(f"Unexpected Gemini response: {json.dumps(body)[:500]}", file=sys.stderr)
        return 1

    out_path = os.environ.get("REVIEW_OUTPUT", "review.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(review_text.strip())
        f.write("\n")

    print(f"Wrote review to {out_path} ({len(review_text)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
