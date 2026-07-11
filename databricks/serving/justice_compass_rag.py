"""
Justice Compass RAG — MLflow pyfunc for Model Serving.

Bundles gold_embeddings parquet at register time; at inference uses
Databricks Foundation Model endpoints via mlflow.deployments client.
"""

from __future__ import annotations

import json
import math
from typing import Any

import mlflow.pyfunc
import pandas as pd

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


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _deploy_client():
    """Get MLflow deployments client with version compatibility and explicit auth."""
    import os
    
    # Set MLflow tracking URI if not set (Model Serving environment)
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        # In Model Serving, use databricks URI
        os.environ["MLFLOW_TRACKING_URI"] = "databricks"
    
    try:
        # MLflow >= 2.9 (newer API)
        from mlflow.deployments import get_deploy_client
        return get_deploy_client("databricks")
    except (ImportError, AttributeError):
        # MLflow < 2.9 (legacy API)
        try:
            from mlflow.deployments import get_deployments_client
            return get_deployments_client("databricks")
        except (ImportError, AttributeError):
            # Fallback for very old versions
            import mlflow.deployments
            return mlflow.deployments.get_deploy_client("databricks")


def _extract_embedding(response: Any) -> list[float]:
    if isinstance(response, list):
        if response and isinstance(response[0], (int, float)):
            return list(response)
        if response and isinstance(response[0], dict):
            return _extract_embedding(response[0])
    if isinstance(response, dict):
        for key in ("embedding", "embeddings", "data"):
            if key in response:
                return _extract_embedding(response[key])
        if "predictions" in response:
            return _extract_embedding(response["predictions"])
    raise ValueError(f"Unexpected embedding response shape: {type(response)}")


def embed_text(text: str) -> list[float]:
    client = _deploy_client()
    response = client.predict(endpoint=EMBED_MODEL, inputs={"input": [text]})
    embedding = _extract_embedding(response)
    if isinstance(embedding, list) and embedding and isinstance(embedding[0], list):
        return embedding[0]
    return list(embedding)


def generate_answer(prompt: str) -> str:
    client = _deploy_client()
    try:
        response = client.predict(
            endpoint=LLM_MODEL,
            inputs={"messages": [{"role": "user", "content": prompt}]},
        )
    except Exception:
        response = client.predict(endpoint=LLM_MODEL, inputs={"prompt": prompt})

    if isinstance(response, dict):
        if "choices" in response:
            return response["choices"][0]["message"]["content"]
        if "predictions" in response:
            pred = response["predictions"]
            if isinstance(pred, list) and pred:
                item = pred[0]
                return item if isinstance(item, str) else item.get("answer", str(item))
        if "answer" in response:
            return response["answer"]
    if isinstance(response, list) and response:
        item = response[0]
        return item if isinstance(item, str) else str(item)
    return str(response)


def build_context(chunks: pd.DataFrame) -> str:
    blocks = []
    for row in chunks.itertuples(index=False):
        blocks.append(
            f"Case: {row.title}\n"
            f"Citation: {row.citation}\n"
            f"URL: {row.canlii_url}\n"
            f"Excerpt: {row.chunk_text}"
        )
    return "\n\n---\n\n".join(blocks)


def rag_query(chunks: pd.DataFrame, question: str, top_k: int = TOP_K) -> dict:
    q_emb = embed_text(question)
    scored = []
    for row in chunks.itertuples(index=False):
        emb = row.embedding
        if isinstance(emb, str):
            emb = json.loads(emb)
        scored.append((cosine_similarity(q_emb, list(emb)), row))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [r for _, r in scored[:top_k]]

    context = build_context(pd.DataFrame(top))
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )
    answer = generate_answer(prompt)
    citations = [
        {
            "case_name": r.title,
            "citation": r.citation,
            "url": r.canlii_url,
            "snippet": (r.chunk_text or "")[:240],
        }
        for r in top
    ]
    return {
        "question": question,
        "answer": answer,
        "citations": citations,
        "mock": False,
    }


class JusticeCompassRAG(mlflow.pyfunc.PythonModel):
    """Serve RAG queries for Cloudflare Worker."""

    def load_context(self, context: mlflow.pyfunc.PythonModelContext) -> None:
        path = context.artifacts["gold_embeddings"]
        self.chunks = pd.read_parquet(path)

    def predict(
        self, context: mlflow.pyfunc.PythonModelContext, model_input: pd.DataFrame
    ) -> pd.DataFrame:
        if "question" not in model_input.columns:
            raise ValueError("model_input must include column: question")
        question = str(model_input["question"].iloc[0]).strip()
        if not question:
            raise ValueError("question must not be empty")
        result = rag_query(self.chunks, question)
        return pd.DataFrame(
            [
                {
                    "answer": result["answer"],
                    "citations": result["citations"],
                    "mock": result["mock"],
                }
            ]
        )
