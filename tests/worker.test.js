import { describe, it } from "node:test";
import assert from "node:assert/strict";

import worker, {
  buildQueryLogEntry,
  checkAuth,
  MOCK_RESPONSE,
  parseServingResponse,
} from "../cloudflare/worker/src/index.js";

describe("Worker health", () => {
  it("returns ok on /health", async () => {
    const req = new Request("http://localhost/health");
    const res = await worker.fetch(req, {});
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, "ok");
    assert.equal(body.service, "justice-compass-api");
  });
});

describe("Worker query", () => {
  it("returns mock response when Databricks not configured", async () => {
    const req = new Request("http://localhost/query?q=revoke+licence");
    const res = await worker.fetch(req, {});
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.ok(body.answer);
    assert.equal(body.mock, true);
    assert.ok(Array.isArray(body.citations));
  });

  it("rejects missing query", async () => {
    const req = new Request("http://localhost/query");
    const res = await worker.fetch(req, {});
    assert.equal(res.status, 400);
  });

  it("requires auth when API_KEY set", async () => {
    const req = new Request("http://localhost/query?q=test");
    const res = await worker.fetch(req, { API_KEY: "secret" });
    assert.equal(res.status, 401);
  });
});

describe("checkAuth", () => {
  it("passes when no API_KEY configured", () => {
    const req = new Request("http://localhost/query");
    assert.equal(checkAuth(req, {}), true);
  });

  it("passes with correct bearer token", () => {
    const req = new Request("http://localhost/query", {
      headers: { Authorization: "Bearer secret" },
    });
    assert.equal(checkAuth(req, { API_KEY: "secret" }), true);
  });
});

describe("parseServingResponse", () => {
  it("parses MLflow predictions array", () => {
    const out = parseServingResponse({
      predictions: [
        {
          answer: "Live answer",
          citations: [{ case_name: "A v B", url: "https://example.com" }],
        },
      ],
    });
    assert.equal(out.answer, "Live answer");
    assert.equal(out.citations.length, 1);
    assert.equal(out.mock, false);
  });

  it("parses citations JSON string", () => {
    const out = parseServingResponse({
      predictions: [{ answer: "x", citations: '[{"case_name":"C"}]' }],
    });
    assert.equal(out.citations[0].case_name, "C");
  });
});

describe("Worker meta", () => {
  it("returns freshness fields on /meta", async () => {
    const req = new Request("http://localhost/meta");
    const res = await worker.fetch(req, {});
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.ok("model_last_updated" in body);
    assert.ok("docs_last_updated" in body);
    assert.ok("model_version" in body);
    assert.ok("case_count" in body);
    assert.ok("cases_last_updated" in body);
  });
});

describe("casesTableSql", () => {
  it("defaults to quoted default.cases_meta_synced Synced Table", async () => {
    const { casesTableSql } = await import("../cloudflare/worker/src/meta.js");
    assert.equal(casesTableSql({}), '"default".cases_meta_synced');
    assert.equal(
      casesTableSql({ LAKEBASE_CASES_TABLE: "default.cases_meta_synced" }),
      '"default".cases_meta_synced'
    );
    assert.equal(casesTableSql({ LAKEBASE_CASES_TABLE: "public.cases" }), '"public"."cases"');
  });
});

describe("buildQueryLogEntry", () => {
  it("builds audit fields from RAG response", () => {
    const entry = buildQueryLogEntry(
      "When revoke licence?",
      {
        answer: "Because of violations.",
        citations: [{ case_name: "A" }, { case_name: "B" }],
        mock: false,
      },
      1234.7
    );
    assert.equal(entry.question, "When revoke licence?");
    assert.equal(entry.answer_preview, "Because of violations.");
    assert.equal(entry.citation_count, 2);
    assert.equal(entry.mock_mode, false);
    assert.equal(entry.latency_ms, 1235);
  });

  it("truncates long answers", () => {
    const entry = buildQueryLogEntry("q", { answer: "x".repeat(600), mock: true }, 1);
    assert.equal(entry.answer_preview.length, 500);
    assert.equal(entry.mock_mode, true);
  });
});

describe("MOCK_RESPONSE", () => {
  it("has required fields", () => {
    assert.ok(MOCK_RESPONSE.answer);
    assert.ok(MOCK_RESPONSE.citations.length > 0);
  });
});
