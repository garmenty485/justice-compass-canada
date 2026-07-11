/**
 * Freshness metadata for homepage (/meta).
 * Model: MLflow registered model API.
 * Docs: SQL warehouse query on Lakebase pipeline_runs (UC three-part name).
 * Corpus: Synced Table in Lakebase (default: "default".cases_meta_synced — NOT public.cases DDL).
 */

import { createLakebaseSql, lakebaseConfigured } from "./query_log.js";

const DEFAULT_UC_MODEL = "workspace.default.justice_compass_rag";
/** Synced Table from Delta cases_metadata → Lakebase (schema "default" is reserved → quote). */
const DEFAULT_CASES_TABLE = '"default".cases_meta_synced';

function workspaceHostFromServingUrl(servingUrl) {
  if (!servingUrl) return null;
  try {
    return new URL(servingUrl).host;
  } catch {
    return null;
  }
}

function apiRoot(env) {
  const host =
    env.DATABRICKS_HOST ||
    workspaceHostFromServingUrl(env.DATABRICKS_SERVING_URL);
  return host ? `https://${host}` : null;
}

function authHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function fetchModelMeta(env) {
  const token = env.DATABRICKS_TOKEN;
  const root = apiRoot(env);
  if (!token || !root) return null;

  const modelName = env.UC_MODEL_NAME || DEFAULT_UC_MODEL;
  const url = `${root}/api/2.0/mlflow/registered-models/get?name=${encodeURIComponent(modelName)}`;
  const res = await fetch(url, { headers: authHeaders(token) });
  if (!res.ok) return null;

  const data = await res.json();
  const versions = data.registered_model?.latest_versions ?? [];
  if (!versions.length) return null;

  const latest = versions.reduce((a, b) =>
    Number(a.version) >= Number(b.version) ? a : b
  );
  const ts = latest.creation_timestamp;
  return {
    model_version: String(latest.version),
    model_last_updated: ts ? new Date(ts).toISOString() : null,
  };
}

async function pollStatement(root, token, statementId) {
  const url = `${root}/api/2.0/sql/statements/${statementId}`;
  for (let i = 0; i < 20; i++) {
    const res = await fetch(url, { headers: authHeaders(token) });
    if (!res.ok) return null;
    const data = await res.json();
    const state = data.status?.state;
    if (state === "SUCCEEDED") return data;
    if (state === "FAILED" || state === "CANCELED") return null;
    await new Promise((r) => setTimeout(r, 500));
  }
  return null;
}

async function fetchDocsMeta(env) {
  const token = env.DATABRICKS_TOKEN;
  const warehouseId = env.DATABRICKS_WAREHOUSE_ID;
  const table = env.LAKEBASE_PIPELINE_RUNS_TABLE;
  const root = apiRoot(env);
  if (!token || !root || !warehouseId || !table) return null;

  const statement = `
    SELECT MAX(finished_at) AS docs_last_updated
    FROM ${table}
    WHERE layer = 'gold' AND status = 'success'
  `.trim();

  const res = await fetch(`${root}/api/2.0/sql/statements/`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      warehouse_id: warehouseId,
      statement,
      wait_timeout: "30s",
    }),
  });
  if (!res.ok) return null;

  let data = await res.json();
  if (data.status?.state !== "SUCCEEDED" && data.statement_id) {
    data = (await pollStatement(root, token, data.statement_id)) ?? data;
  }
  if (data.status?.state !== "SUCCEEDED") return null;

  const row = data.result?.data_array?.[0];
  const raw = row?.[0];
  if (!raw) return null;
  return { docs_last_updated: new Date(raw).toISOString() };
}

/**
 * Resolve Synced Table identifier for corpus stats.
 * Default: "default".cases_meta_synced (Lakebase Synced Table from cases_metadata).
 * Override with LAKEBASE_CASES_TABLE (must be a safe schema.table; "default" is quoted).
 */
function casesTableSql(env) {
  const raw = (env.LAKEBASE_CASES_TABLE || DEFAULT_CASES_TABLE).trim();
  // Allow "default".cases_meta_synced or default.cases_meta_synced or public.cases
  if (/^["']?default["']?\s*\.\s*cases_meta_synced$/i.test(raw)) {
    return '"default".cases_meta_synced';
  }
  if (/^["']?default["']?\s*\.\s*cases$/i.test(raw)) {
    return '"default".cases';
  }
  if (/^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$/i.test(raw)) {
    const [schema, table] = raw.split(".");
    return `"${schema}"."${table}"`;
  }
  return DEFAULT_CASES_TABLE;
}

async function fetchCasesMeta(env) {
  if (!lakebaseConfigured(env)) return null;

  let sql;
  try {
    sql = await createLakebaseSql(env);
    const table = casesTableSql(env);
    // Identifier from allowlisted env only — not user input
    const rows = await sql.unsafe(`
      SELECT COUNT(*)::int AS case_count, MAX(ingested_at) AS cases_last_updated
      FROM ${table}
    `);
    const row = rows[0];
    if (!row) return null;
    const casesLastUpdated = row.cases_last_updated
      ? new Date(row.cases_last_updated).toISOString()
      : null;
    return {
      case_count: Number(row.case_count) || 0,
      cases_last_updated: casesLastUpdated,
    };
  } catch (err) {
    console.error("cases meta query failed:", err.message);
    return null;
  } finally {
    if (sql) {
      try {
        await sql.end({ timeout: 5 });
      } catch {
        /* ignore close errors */
      }
    }
  }
}

async function buildMetaResponse(env) {
  const [modelMeta, docsMeta, casesMeta] = await Promise.all([
    fetchModelMeta(env),
    fetchDocsMeta(env),
    fetchCasesMeta(env),
  ]);

  return {
    model_version: modelMeta?.model_version ?? null,
    model_last_updated: modelMeta?.model_last_updated ?? null,
    docs_last_updated: docsMeta?.docs_last_updated ?? null,
    case_count: casesMeta?.case_count ?? null,
    cases_last_updated: casesMeta?.cases_last_updated ?? null,
    sources: {
      model: modelMeta ? "mlflow" : null,
      docs: docsMeta ? "lakebase_via_sql" : null,
      cases: casesMeta ? "lakebase_synced_table" : null,
    },
  };
}

export {
  apiRoot,
  buildMetaResponse,
  casesTableSql,
  fetchCasesMeta,
  fetchDocsMeta,
  fetchModelMeta,
  workspaceHostFromServingUrl,
};
