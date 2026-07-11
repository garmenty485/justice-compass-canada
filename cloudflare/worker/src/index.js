/**
 * Justice Compass API — Cloudflare Worker
 * Proxies queries to Databricks Model Serving; falls back to mock in dev.
 *
 * Note (dev-test-ai-PR-review): health exposes lakebase_configured for ops checks only.
 */

import { buildMetaResponse } from "./meta.js";
import { buildQueryLogEntry, insertQueryLog, lakebaseConfigured } from "./query_log.js";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

const MOCK_RESPONSE = {
  answer:
    "Under BC's liquor licensing framework, the Liquor Control and Licensing Branch may revoke a licence when the licensee repeatedly fails to comply with the Liquor Control and Licensing Act or its terms and conditions. Revocation requires procedural fairness, including notice of allegations and an opportunity to respond. Courts review such decisions on the standard of reasonableness (sample response — connect Databricks for live RAG).",
  citations: [
    {
      case_name: "Pacific Hospitality Ltd. v. Liquor Control and Licensing Branch",
      citation: "2020 BCSC 123",
      url: "https://justice-compass.demo/cases/2020bcsc123",
      snippet:
        "The Branch must afford procedural fairness before revocation, including notice of allegations and an opportunity to respond.",
    },
  ],
  mock: true,
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

function unauthorized() {
  return jsonResponse({ error: "Unauthorized" }, 401);
}

function checkAuth(request, env) {
  const expected = env.API_KEY;
  if (!expected) return true;
  const auth = request.headers.get("Authorization");
  return auth === `Bearer ${expected}`;
}

async function queryDatabricks(question, env) {
  const url = env.DATABRICKS_SERVING_URL;
  const token = env.DATABRICKS_TOKEN;
  if (!url || !token) return null;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        inputs: { question: [question] },
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`Databricks serving error: ${res.status} ${detail}`.trim());
    }

    const data = await res.json();
    return parseServingResponse(data);
  } finally {
    clearTimeout(timeout);
  }
}

function parseServingResponse(data) {
  let row = data;
  if (Array.isArray(data?.predictions) && data.predictions.length > 0) {
    row = data.predictions[0];
  } else if (data?.predictions && typeof data.predictions === "object") {
    row = data.predictions;
  }

  let citations = row?.citations ?? data?.citations ?? [];
  if (typeof citations === "string") {
    try {
      citations = JSON.parse(citations);
    } catch {
      citations = [];
    }
  }

  return {
    answer: row?.answer ?? data?.answer ?? "",
    citations,
    mock: false,
  };
}

async function handleQuery(request, env, ctx) {
  let question = "";
  const contentType = request.headers.get("Content-Type") ?? "";

  if (request.method === "GET") {
    question = new URL(request.url).searchParams.get("q") ?? "";
  } else if (contentType.includes("application/json")) {
    const body = await request.json();
    question = body.question ?? body.q ?? "";
  }

  question = question.trim();
  if (!question) {
    return jsonResponse({ error: "Missing query parameter: q or question" }, 400);
  }

  const started = Date.now();

  try {
    const live = await queryDatabricks(question, env);
    const result = live ?? { ...MOCK_RESPONSE, question };
    const latencyMs = Date.now() - started;

    if (ctx?.waitUntil) {
      ctx.waitUntil(
        insertQueryLog(env, buildQueryLogEntry(question, result, latencyMs))
      );
    }

    if (live) return jsonResponse(live);
    return jsonResponse(result);
  } catch (err) {
    return jsonResponse(
      { error: "Upstream error", message: err.message, fallback: MOCK_RESPONSE },
      502
    );
  }
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return jsonResponse({
        status: "ok",
        service: "justice-compass-api",
        databricks_configured: Boolean(env.DATABRICKS_SERVING_URL && env.DATABRICKS_TOKEN),
        lakebase_configured: lakebaseConfigured(env),
      });
    }

    if (url.pathname === "/meta" || url.pathname === "/api/meta") {
      try {
        const meta = await buildMetaResponse(env);
        return jsonResponse(meta);
      } catch (err) {
        return jsonResponse({ error: "Meta unavailable", message: err.message }, 502);
      }
    }

    if (url.pathname === "/query" || url.pathname === "/api/query") {
      if (!checkAuth(request, env)) return unauthorized();
      if (request.method !== "GET" && request.method !== "POST") {
        return jsonResponse({ error: "Method not allowed" }, 405);
      }
      return handleQuery(request, env, ctx);
    }

    return jsonResponse({ error: "Not found" }, 404);
  },
};

export {
  buildMetaResponse,
  buildQueryLogEntry,
  checkAuth,
  handleQuery,
  insertQueryLog,
  MOCK_RESPONSE,
  parseServingResponse,
};
