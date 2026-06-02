"""Data model for the catalog.

Plain dataclasses, no DB or third-party types, so the inference, classify
and render logic can be unit-tested without a database connection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Column:
    """A single column, plus optional profile and semantic annotations."""

    schema: str
    table: str
    name: str
    ordinal: int
    data_type: str
    is_nullable: bool
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    default: Optional[str] = None
    is_identity: bool = False
    is_primary_key: bool = False

    # --- profile (filled by the profile phase; all sample-based) ---
    sampled_rows: Optional[int] = None
    null_count: Optional[int] = None
    distinct_count: Optional[int] = None
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    sample_values: list = field(default_factory=list)

    # --- annotations (filled by classify / semantic phases) ---
    is_pii: bool = False
    pii_kind: Optional[str] = None
    description: Optional[str] = None

    @property
    def qualified_table(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def null_pct(self) -> Optional[float]:
        if self.sampled_rows and self.sampled_rows > 0 and self.null_count is not None:
            return round(100.0 * self.null_count / self.sampled_rows, 2)
        return None

    @property
    def is_numeric(self) -> bool:
        t = self.data_type.lower()
        return any(
            k in t
            for k in ("int", "decimal", "numeric", "float", "real", "money", "bit")
        )

    @property
    def is_temporal(self) -> bool:
        t = self.data_type.lower()
        return any(k in t for k in ("date", "time"))


@dataclass
class ForeignKey:
    """A relationship between two columns.

    ``inferred`` distinguishes a declared FK (read from the catalog,
    confidence 1.0) from one this tool guessed. ``confidence`` and
    ``reason`` explain a guess so a human can accept or reject it.
    """

    name: str
    parent_schema: str
    parent_table: str
    parent_column: str
    ref_schema: str
    ref_table: str
    ref_column: str
    inferred: bool = False
    confidence: float = 1.0
    reason: str = "declared"

    @property
    def parent_qualified(self) -> str:
        return f"{self.parent_schema}.{self.parent_table}"

    @property
    def ref_qualified(self) -> str:
        return f"{self.ref_schema}.{self.ref_table}"


@dataclass
class Table:
    schema: str
    name: str
    row_count: int = 0
    columns: list = field(default_factory=list)
    primary_key: list = field(default_factory=list)
    foreign_keys: list = field(default_factory=list)

    # classify phase
    kind: str = "unknown"  # fact / dimension / bridge / reference / unknown
    subject_area: Optional[str] = None
    description: Optional[str] = None

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def column(self, name: str) -> Optional[Column]:
        for c in self.columns:
            if c.name.lower() == name.lower():
                return c
        return None


@dataclass
class Catalog:
    tables: list = field(default_factory=list)
    # every relationship, declared and inferred
    relationships: list = field(default_factory=list)

    def table_map(self) -> dict:
        return {t.qualified_name: t for t in self.tables}

    def get(self, schema: str, name: str) -> Optional[Table]:
        return self.table_map().get(f"{schema}.{name}")
