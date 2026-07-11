/**
 * Write RAG query audit rows to Lakebase query_logs (Postgres direct).
 * Requires LAKEBASE_* secrets — see docs/LAKEBASE.md.
 *
 * Fire-and-forget via ctx.waitUntil in index.js — failures are logged, not surfaced to clients.
 */

const ANSWER_PREVIEW_MAX = 500;

function lakebaseConfigured(env) {
  return Boolean(
    env.LAKEBASE_HOST &&
      env.LAKEBASE_DB &&
      env.LAKEBASE_USER &&
      env.LAKEBASE_PASSWORD
  );
}

function buildQueryLogEntry(question, result, latencyMs) {
  const answer = result?.answer ?? "";
  const citations = result?.citations;
  return {
    question: String(question).slice(0, 4000),
    answer_preview: String(answer).slice(0, ANSWER_PREVIEW_MAX),
    citation_count: Array.isArray(citations) ? citations.length : 0,
    mock_mode: Boolean(result?.mock),
    latency_ms: Number.isFinite(latencyMs) ? Math.max(0, Math.round(latencyMs)) : null,
  };
}

function createLakebaseSql(env) {
  if (!lakebaseConfigured(env)) return null;

  // Dynamic import keeps unit tests free of postgres when not logging.
  return import("postgres").then(({ default: postgres }) =>
    postgres({
      host: env.LAKEBASE_HOST,
      database: env.LAKEBASE_DB,
      username: env.LAKEBASE_USER,
      password: env.LAKEBASE_PASSWORD,
      port: 5432,
      ssl: "require",
      max: 1,
      connect_timeout: 10,
      idle_timeout: 5,
    })
  );
}

async function insertQueryLog(env, entry) {
  if (!lakebaseConfigured(env)) return false;

  let sql;
  try {
    sql = await createLakebaseSql(env);
    await sql`
      INSERT INTO query_logs (question, answer_preview, citation_count, mock_mode, latency_ms)
      VALUES (
        ${entry.question},
        ${entry.answer_preview},
        ${entry.citation_count},
        ${entry.mock_mode},
        ${entry.latency_ms}
      )
    `;
    return true;
  } catch (err) {
    console.error("query_logs insert failed:", err.message);
    return false;
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

export {
  ANSWER_PREVIEW_MAX,
  buildQueryLogEntry,
  createLakebaseSql,
  insertQueryLog,
  lakebaseConfigured,
};
