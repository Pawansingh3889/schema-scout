"""Compare two catalog snapshots and report what changed (schema / data drift).

schema-scout produces a one-off picture of a database. Databases change over
time: columns get added, types change, tables grow or empty out, and an old
readiness score stops matching reality. ``diff_catalogs`` takes two saved
catalogs (older and newer) and reports the differences, including the change in
the readiness score.

Pure function over two in-memory ``Catalog`` objects, so it's testable without
a database. Load saved snapshots with ``catalog_io.load_catalog`` and pass them
in.
"""
from __future__ import annotations

from schema_scout import readiness
from schema_scout.model import Catalog, Column, Table


def _col_map(table: Table) -> dict:
    return {c.name.lower(): c for c in table.columns}


def _col_view(c: Column) -> dict:
    return {
        "data_type": c.data_type,
        "nullable": c.is_nullable,
        "primary_key": c.is_primary_key,
    }


def _pct_change(old: int, new: int):
    # None when there's no meaningful base to compare against (old was empty).
    if old == 0:
        return None
    return round(100.0 * (new - old) / old, 1)


def diff_catalogs(old: Catalog, new: Catalog, row_change_threshold: float = 25.0) -> dict:
    """Return a structured diff of two catalogs (old -> new).

    row_change_threshold is the percentage row-count move that gets flagged as
    "significant" (a table doubling or halving is usually worth a look).
    """
    old_tables = old.table_map()
    new_tables = new.table_map()
    old_names = set(old_tables)
    new_names = set(new_tables)

    added = sorted(new_names - old_names)
    removed = sorted(old_names - new_names)

    changed = []
    cols_added_total = cols_removed_total = cols_changed_total = 0

    for name in sorted(old_names & new_names):
        ot, nt = old_tables[name], new_tables[name]
        oc, nc = _col_map(ot), _col_map(nt)

        c_added = sorted(set(nc) - set(oc))
        c_removed = sorted(set(oc) - set(nc))
        c_changed = []
        for key in sorted(set(oc) & set(nc)):
            ov, nv = _col_view(oc[key]), _col_view(nc[key])
            if ov != nv:
                fields = [k for k in ov if ov[k] != nv[k]]
                c_changed.append(
                    {"column": nc[key].name, "from": ov, "to": nv, "changed": fields}
                )

        row_change = None
        if ot.row_count != nt.row_count:
            pct = _pct_change(ot.row_count, nt.row_count)
            row_change = {
                "from": ot.row_count,
                "to": nt.row_count,
                "delta": nt.row_count - ot.row_count,
                "pct": pct,
                "significant": pct is None or abs(pct) >= row_change_threshold,
            }

        if c_added or c_removed or c_changed or row_change:
            changed.append(
                {
                    "table": name,
                    "columns_added": [nc[k].name for k in c_added],
                    "columns_removed": [oc[k].name for k in c_removed],
                    "columns_changed": c_changed,
                    "row_count": row_change,
                }
            )
            cols_added_total += len(c_added)
            cols_removed_total += len(c_removed)
            cols_changed_total += len(c_changed)

    r_old = readiness.compute_readiness(old)
    r_new = readiness.compute_readiness(new)
    readiness_diff = {
        "from": r_old["score"],
        "to": r_new["score"],
        "delta": round(r_new["score"] - r_old["score"], 1),
        "components": {
            k: {
                "from": r_old["components"][k],
                "to": r_new["components"][k],
                "delta": round(r_new["components"][k] - r_old["components"][k], 1),
            }
            for k in r_old["components"]
        },
    }

    return {
        "tables": {"added": added, "removed": removed, "changed": changed},
        "readiness": readiness_diff,
        "summary": {
            "tables_added": len(added),
            "tables_removed": len(removed),
            "tables_changed": len(changed),
            "columns_added": cols_added_total,
            "columns_removed": cols_removed_total,
            "columns_changed": cols_changed_total,
            "readiness_delta": readiness_diff["delta"],
        },
    }


def has_changes(d: dict) -> bool:
    s = d["summary"]
    return bool(
        s["tables_added"]
        or s["tables_removed"]
        or s["tables_changed"]
        or s["readiness_delta"]
    )


def format_diff(d: dict) -> str:
    """Render a diff dict as readable text."""
    r = d["readiness"]
    t = d["tables"]
    lines = [f"Readiness: {r['from']} -> {r['to']} ({r['delta']:+})"]

    moved = [
        f"{k} {v['from']}->{v['to']}"
        for k, v in r["components"].items()
        if v["delta"] != 0
    ]
    if moved:
        lines.append("  components moved: " + ", ".join(moved))

    if t["added"]:
        lines.append(f"Tables added ({len(t['added'])}): " + ", ".join(t["added"]))
    if t["removed"]:
        lines.append(f"Tables removed ({len(t['removed'])}): " + ", ".join(t["removed"]))

    for ch in t["changed"]:
        lines.append(f"~ {ch['table']}")
        if ch["columns_added"]:
            lines.append("    + columns: " + ", ".join(ch["columns_added"]))
        if ch["columns_removed"]:
            lines.append("    - columns: " + ", ".join(ch["columns_removed"]))
        for cc in ch["columns_changed"]:
            detail = ", ".join(
                f"{k} {cc['from'][k]}->{cc['to'][k]}" for k in cc["changed"]
            )
            lines.append(f"    * {cc['column']}: {detail}")
        rc = ch["row_count"]
        if rc:
            pct = "" if rc["pct"] is None else f" ({rc['pct']:+}%)"
            flag = "  [significant]" if rc["significant"] else ""
            lines.append(f"    rows: {rc['from']:,} -> {rc['to']:,}{pct}{flag}")

    if not has_changes(d):
        lines.append("No changes.")
    return "\n".join(lines)
