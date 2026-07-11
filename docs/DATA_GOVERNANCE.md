# Data Governance

## Catalog

- **MVP (Free Edition)**: default catalog — `workspace.default.bronze_cases`, `silver_chunks`, `gold_embeddings`

## Naming conventions

| Object | Pattern | MVP example |
|--------|---------|---------------|
| Bronze table | `{entity}_cases` | `bronze_cases` |
| Silver table | `{entity}_chunks` | `silver_chunks` |
| Gold table | `{entity}_embeddings` | `gold_embeddings` |
| Column IDs | `snake_case` | `case_id`, `chunk_id` |

## Data ingress

- Sample cases: **Git folder** `data/sample/*.json` — **synthetic demo corpus** (8 BC liquor-licensing cases)

## Lineage

```
Git data/sample/*.json → bronze_cases → silver_chunks → gold_embeddings → RAG (04 / Serving)
```

## Quality checks (Phase 1+)

- `fullText` not empty
- Valid `citation` format
- `canlii_url` / demo URL present (optional HTTP check)

Scores stored in `data_quality_scores` (Lakebase) or Delta audit table.

## Retention

- Sample MVP: static synthetic snapshot in Git
- No external API ingestion; redeploy Serving after corpus changes
