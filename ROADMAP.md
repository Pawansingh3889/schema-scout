# Roadmap

schema-scout is young and deliberately narrow: it reverse-engineers a SQL
Server schema into a catalog you can read. This is where it's going. Nothing
here is a promise with a date on it, it's the order I'd tackle things in.

## Done

- Structure extraction from the system catalog (tables, columns, PKs, FKs, row counts)
- Sampled and exact column profiling
- Inference of undeclared foreign keys, with an optional value-inclusion check
- Table classification (fact / dimension / bridge / reference) and PII flagging
- Subject-area (domain) grouping
- Health checks (no PK, orphan, all-null, constant, mostly-null)
- Join-path finder between any two tables
- On-prem table descriptions via a local Ollama model
- Outputs: self-contained HTML dashboard, JSON, Markdown, Mermaid ERD, FK-constraint SQL, dbt relationship tests

## Next

The biggest one first.

- **More databases.** Today it's SQL Server only. The structure pass uses
  `sys.*`; most of it has an `INFORMATION_SCHEMA` equivalent. Adding
  PostgreSQL and MySQL (then Snowflake / BigQuery) behind a small dialect
  interface is the single change that makes this useful to far more people.
  It needs real test databases per engine, so it's its own piece of work.
- **Publish to PyPI** so it's `pip install schema-scout`, with versioned
  releases and a changelog.
- **Docker image** for one-command runs without a local Python setup.
- **More docs:** an architecture diagram, a short FAQ (how fast, how big a
  schema), a troubleshooting note for ODBC driver issues, and a couple of
  committed example outputs.

## Later

- Schema-change history: snapshot the catalog and diff two runs (added/removed
  tables and columns, type changes, new PII).
- A printable data dictionary (PDF) and a CSV/Excel column inventory for
  non-technical stakeholders.
- Column-level lineage from view and query-text analysis.
- PII scoring and anonymization: distribution-based column scoring (so a
  product name that collides with a surname is not flagged), a quasi-identifier
  and k-anonymity table pass for the mosaic effect, and a greedy generalization
  suggester. Design in [docs/pii-anonymization-design.md](docs/pii-anonymization-design.md).
- More LLM providers for the descriptions step, not just Ollama.
- Deeper dbt integration and an OpenMetadata export.
- Custom, pluggable inference and classification rules.

## Maybe, much later

A hosted version for teams who don't want to run it themselves. Only worth it
if enough people are using the open-source tool first.

---

Ideas and contributions welcome, see [CONTRIBUTING.md](CONTRIBUTING.md).
