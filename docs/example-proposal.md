# Proposal: A Data Catalog & Governance Baseline (Example)

**Prepared by:** Pawan Kapkoti
**For:** IT Manager · Finance · HR / Compliance
**Status:** Proof-of-concept complete — seeking endorsement to formalize

> **Example documentation.** Database name (`DemoDB`), server (`demo-sql01`) and
> all figures below are fictional samples that illustrate how a real proposal
> built from a schema-scout run would read. Replace with your own results.

---

## 1. Executive summary

The `DemoDB` SQL Server platform has grown to **~312 tables and ~84 million
rows**, but almost none of it is documented and most relationships between
tables were never formally declared. This slows analyst onboarding, makes
reporting error-prone, and blocks safe use of AI / agentic tooling, which can
only work against data it can understand.

As a low-risk proof-of-concept, an **open-source, read-only** cataloging tool
(*schema-scout*) was run against `DemoDB`. In a single pass, with no changes to
the database and nothing leaving the machine, it produced a full data catalog,
mapped hidden relationships, and **flagged ~137 columns likely to contain
personal data (PII)** that should be tracked for compliance.

The recommendation is to **formalize this as a small, recurring data-governance
practice.** The tooling is free and on-premise; the main investment is a modest
amount of analyst time. The payoff is faster delivery, lower reporting risk,
and a defensible record of where personal data lives.

---

## 2. The opportunity

| Today | With a maintained catalog |
|---|---|
| ~312 tables, **0% documented** | Plain-English description of every table |
| Relationships mostly undeclared | Hidden joins recovered and mapped |
| **~137 potential PII columns** untracked | PII inventory for data-protection compliance |
| New analysts reverse-engineer the schema by hand | Searchable catalog + diagram on day one |
| Data not "AI-ready" (readiness score **41/100**) | A measurable score we can improve over time |

The initial scan scored the schema **41/100** for AI/analytics readiness — a
**baseline** to track and improve, with concrete, prioritized fixes identified.

---

## 3. What the proof-of-concept found (read-only, no data moved)

- **~312 tables / ~84M rows** catalogued from system metadata (no table scans).
- **~38 relationships** mapped, including **~12 that were never declared** in
  the database and were previously invisible.
- **~137 columns flagged as likely PII** — the starting point for a record of
  where personal data is held.
- **~226 data-quality / structural issues** (~78 high severity), e.g. tables
  with no primary key and a number of empty / backup tables to clean up.
- Outputs: an offline dashboard, a machine-readable catalog, an ER diagram, and
  a reviewable SQL script of suggested relationships for the DBA.

> All access was **read-only** (SELECT only), and any AI-generated
> documentation runs on a **local** model — no schema or data leaves the
> machine.

---

## 4. Why this matters to each team

### For IT
- **Zero-risk operation:** read-only connection, no schema changes, uses
  partition statistics rather than heavy `COUNT(*)` scans — negligible load.
- **Actionable output for the DBA:** a reviewable `ALTER TABLE` script for the
  missing foreign keys, plus a prioritized health/clean-up list.
- **AI-readiness foundation:** a prerequisite for any future agent / NL-to-SQL
  or analytics-automation work, done safely on-prem.

### For Finance
- **Near-zero software cost** — the toolchain is open-source / already-licensed:

  | Tool | Cost |
  |---|---|
  | schema-scout | Free (open source) |
  | Python, Git, ODBC driver | Free |
  | Ollama + local model | Free, runs on existing hardware |
  | SQL Server Management Studio | Free |
  | Power BI Desktop | Free (sharing needs existing Pro/Premium licences) |

- **No cloud / no per-seat SaaS fees** — runs on hardware already owned.
- **Efficiency saving:** faster analyst onboarding and fewer reporting errors.

### For HR / Compliance
- **PII visibility:** the scan identified **~137 columns** likely holding
  personal data — the basis for a Record of Processing / data-protection
  inventory and data-minimization decisions.
- **Privacy by design:** everything runs **on-premise**; no personal data is
  sent to any third party or cloud AI service.
- **Auditability:** each catalog run is a dated snapshot, evidencing what data
  is held and how it changes over time.

---

## 5. Costs & resourcing

| Item | Estimate |
|---|---|
| Software licences | £0 (open-source / already owned) |
| Infrastructure | Existing hardware; no new spend |
| Initial setup | ~1 day |
| Ongoing effort | ~0.5–1 day per quarter to re-run, review, and act on findings |
| Optional DBA time | To apply the suggested relationship/PK fixes (scheduled, low risk) |

---

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Access to sensitive data | Read-only login; SELECT-only; least-privilege DB role |
| Data leaving the org | Fully on-prem; local AI model; no cloud calls |
| Catalog output contains PII flags | Stored only on approved internal systems |
| Acting on inferred relationships | Inferences flagged with confidence for human review |

---

## 7. Recommended next steps (the ask)

1. **Endorse** formalizing this as a quarterly read-only cataloging practice.
2. **Confirm authorization** for the read-only service account and in-scope
   databases (IT + data owner).
3. **Review the PII inventory** with HR/Compliance and agree what to track.
4. **Schedule DBA review** of the suggested relationship/PK fixes.
5. **Agree an owner** and a light review cadence.
