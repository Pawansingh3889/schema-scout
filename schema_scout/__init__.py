"""schema-scout — reverse-engineer and map large SQL Server schemas.

Built for databases with 150+ tables where you cannot eyeball the schema.
The pipeline is deliberately staged so each part scales independently:

    extract   -> structure from the system catalog (one query per concern,
                 regardless of table count)
    profile   -> sampled per-column stats (null %, cardinality, ranges)
    infer     -> undeclared foreign keys, by name/type heuristics and an
                 optional value-inclusion check
    classify  -> fact / dimension / bridge / reference + PII flags
    render    -> JSON catalog (AI-ready), Markdown docs, Mermaid ER diagram

The structure (extract) phase is pure system-catalog reads and never scans
table data. Profiling is opt-in and sample-based so it stays cheap on a
huge database.
"""

from schema_scout.model import Catalog, Column, ForeignKey, Table

__version__ = "0.1.0"

__all__ = ["Catalog", "Column", "ForeignKey", "Table", "__version__"]
