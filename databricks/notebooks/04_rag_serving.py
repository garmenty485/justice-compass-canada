# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — RAG Query (Notebook)
# MAGIC Retrieve top-k chunks from `gold_embeddings`, generate answer via `ai_query`.
# MAGIC
# MAGIC **Prerequisite**: Run `01` → `02` → `03` first.
# MAGIC
# MAGIC **Retrieval**: notebook cosine on Delta (MVP fallback). Target: AI Search index (Free Edition: 1 endpoint).
# MAGIC
# MAGIC Phase 2 next step: register as Model Serving endpoint for Cloudflare Worker.

# COMMAND ----------

GOLD_TABLE = "gold_embeddings"
EMBED_MODEL = "databricks-gte-large-en"
LLM_MODEL = "databricks-meta-llama-3-1-8b-instruct"
TOP_K = 3

SYSTEM_PROMPT = """You are Justice Compass, an informational assistant summarizing BC liquor licensing case law.

Rules:
- Answer using ONLY the provided context
- Cite cases as markdown links: [Case Name](canlii_url)
- If context is insufficient, say so clearly
- End with: "This is not legal advice."
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## Helpers

# COMMAND ----------

import math


def sql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''")


def embed_query(text: str) -> list[float]:
    safe = sql_escape(text)
    row = spark.sql(
        f"SELECT ai_query('{EMBED_MODEL}', '{safe}') AS embedding"
    ).collect()[0]
    return row.embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(question: str, top_k: int = TOP_K):
    if spark.table(GOLD_TABLE).count() == 0:
        raise RuntimeError(f"{GOLD_TABLE} is empty. Run 03_gold_embed first.")
    q_emb = embed_query(question)
    rows = spark.table(GOLD_TABLE).collect()
    ranked = sorted(
        rows,
        key=lambda r: cosine_similarity(q_emb, r.embedding),
        reverse=True,
    )[:top_k]
    return ranked


def build_context(chunks) -> str:
    blocks = []
    for row in chunks:
        blocks.append(
            f"Case: {row.title}\n"
            f"Citation: {row.citation}\n"
            f"URL: {row.canlii_url}\n"
            f"Excerpt: {row.chunk_text}"
        )
    return "\n\n---\n\n".join(blocks)


def generate_answer(question: str, context: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )
    safe = sql_escape(prompt)
    row = spark.sql(
        f"SELECT ai_query('{LLM_MODEL}', '{safe}') AS answer"
    ).collect()[0]
    return row.answer


def rag_query(question: str) -> dict:
    chunks = retrieve(question)
    context = build_context(chunks)
    answer = generate_answer(question, context)
    citations = [
        {
            "case_name": c.title,
            "citation": c.citation,
            "url": c.canlii_url,
            "snippet": c.chunk_text[:240],
        }
        for c in chunks
    ]
    return {"question": question, "answer": answer, "citations": citations, "mock": False}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo query

# COMMAND ----------

DEMO_QUESTION = "When can BC revoke a liquor licence?"

result = rag_query(DEMO_QUESTION)
print("Question:", result["question"])
print("\nAnswer:\n", result["answer"])
print("\nCitations:")
for c in result["citations"]:
    print(f"- {c['case_name']} ({c['citation']})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optional: test more questions
# MAGIC
# MAGIC ```python
# MAGIC display(spark.createDataFrame([rag_query("What is procedural fairness for LCLB?")]))
# MAGIC ```
