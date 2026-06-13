# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

## [Unreleased]

### Added
- MCP server (`schema-scout-mcp`) so an AI agent can query the catalog live (list/describe tables, find join paths, search, get agent context) — read-only, on-prem
- Catalog loader that reads a generated `catalog.json` back into the model
- Agentic-readiness score (0–100) with a breakdown and fixes, shown on the dashboard and printed by the CLI
- Agent-ready context export (`agent_context.json`) for feeding an LLM doing NL-to-SQL
- Larger multi-domain demo schema (`demo --large`)
- GitHub Actions CI (pytest on Python 3.10–3.13)
- Docker image for running without a local Python setup
- Contributing guide, changelog, issue templates, and a roadmap

## [0.1.0]

### Added
- Structure extraction from the SQL Server system catalog (tables, columns,
  primary keys, foreign keys, row counts)
- Sampled and exact (full-table) column profiling
- Inference of undeclared foreign keys with an optional value-inclusion check
- Table classification (fact / dimension / bridge / reference) and PII flagging
- Subject-area (domain) grouping
- Schema health checks (no PK, orphan, all-null, constant, mostly-null)
- Join-path finder between any two tables
- On-prem table descriptions via a local Ollama model
- Outputs: self-contained HTML dashboard, JSON, Markdown, Mermaid ER diagram,
  FK-constraint SQL script, and dbt relationship tests
