/**
 * Justice Compass — Pages frontend (vanilla JS)
 */

const API_BASE = window.JUSTICE_COMPASS_API ?? "";

const form = document.getElementById("search-form");
const input = document.getElementById("query-input");
const btn = document.getElementById("search-btn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const answerText = document.getElementById("answer-text");
const mockBadge = document.getElementById("mock-badge");
const citationsSection = document.getElementById("citations-section");
const citationsList = document.getElementById("citations-list");

function show(el) {
  el.classList.remove("hidden");
}

function hide(el) {
  el.classList.add("hidden");
}

function setLoading(loading) {
  btn.disabled = loading;
  btn.textContent = loading ? "Searching…" : "Search";
  if (loading) {
    show(statusEl);
    statusEl.textContent = "Searching case law…";
    hide(resultsEl);
  } else {
    hide(statusEl);
  }
}

function renderCitations(citations) {
  citationsList.innerHTML = "";
  if (!citations?.length) {
    hide(citationsSection);
    return;
  }
  citations.forEach((c) => {
    const li = document.createElement("li");
    const title = document.createElement("a");
    title.href = c.url || "#";
    title.target = "_blank";
    title.rel = "noopener";
    title.textContent = `${c.case_name}${c.citation ? ` — ${c.citation}` : ""}`;
    li.appendChild(title);
    if (c.snippet) {
      const snip = document.createElement("p");
      snip.className = "snippet";
      snip.textContent = c.snippet;
      li.appendChild(snip);
    }
    citationsList.appendChild(li);
  });
  show(citationsSection);
}

function renderResult(data) {
  answerText.textContent = data.answer ?? "No answer returned.";
  if (data.mock) show(mockBadge);
  else hide(mockBadge);
  renderCitations(data.citations);
  show(resultsEl);
}

async function search(query) {
  const url = `${API_BASE}/query?q=${encodeURIComponent(query)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q) return;

  setLoading(true);
  try {
    const data = await search(q);
    renderResult(data);
  } catch (err) {
    show(statusEl);
    statusEl.textContent = `Error: ${err.message}`;
  } finally {
    setLoading(false);
  }
});

function formatFreshnessDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return "—";
  }
}

async function loadFreshness() {
  const el = document.getElementById("freshness");
  if (!el || !API_BASE) return;
  try {
    const res = await fetch(`${API_BASE}/meta`);
    if (!res.ok) return;
    const data = await res.json();
    const docs = formatFreshnessDate(data.docs_last_updated);
    const model = formatFreshnessDate(data.model_last_updated);
    const ver = data.model_version ? ` · v${data.model_version}` : "";
    const corpusCount =
      data.case_count != null ? `${data.case_count} cases` : "— cases";
    const corpusSynced = formatFreshnessDate(data.cases_last_updated);
    el.textContent = `Corpus: ${corpusCount} · last synced: ${corpusSynced} · Docs: ${docs} · Model: ${model}${ver}`;
  } catch {
    el.textContent = "";
  }
}

loadFreshness();

export { search, renderResult, renderCitations, loadFreshness, formatFreshnessDate };
