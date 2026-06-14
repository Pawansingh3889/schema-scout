"""Command-line entry point.

Examples
--------
    # see the whole pipeline run on synthetic data, no DB:
    schema-scout demo

    # full run against SQL Server (Windows auth):
    schema-scout run --server localhost --database FactoryDB

    # full run + sampled profiling + on-prem AI descriptions:
    schema-scout run --server localhost --database FactoryDB \
        --profile --describe --model qwen3:14b

A run re-reads the system catalog each time (cheap — it never scans table
data), so there is no intermediate state file to manage.
"""
from __future__ import annotations

import argparse
import os
import sys

from schema_scout import (
    agentcontext,
    classify,
    domains,
    exports,
    extract,
    htmlreport,
    lint,
    paths,
    profile,
    readiness,
    relationships,
    render,
    semantic,
    usage,
)


def _write(outdir: str, name: str, content: str) -> str:
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _run_pipeline(catalog, conn, args) -> None:
    """Annotate ``catalog`` in place per the flags, then render."""
    if args.infer:
        candidates = relationships.infer_relationships(catalog)
        if conn is not None and args.validate:
            for fk in candidates:
                try:
                    ratio = relationships.validate_inclusion(conn, fk)
                    fk.confidence = 0.95 if ratio >= 0.99 else max(fk.confidence, ratio)
                    fk.reason += f"; inclusion {ratio:.0%}"
                except Exception as exc:  # noqa: BLE001 - never fail the run
                    fk.reason += f"; inclusion check failed ({exc})"
        added = relationships.merge_inferred(catalog, candidates, args.min_confidence)
        print(f"  inferred relationships: {len(candidates)} found, {added} kept")

    if conn is not None and args.profile:
        done = profile.profile_catalog(
            conn, catalog, limit=args.profile_limit, sample_size=args.sample_size
        )
        print(f"  profiled {len(done)} tables (sample {args.sample_size:,} rows)")

    if conn is not None and (args.exact or args.exact_keys):
        keys_only = args.exact_keys and not args.exact
        done = profile.profile_catalog_exact(
            conn, catalog, limit=args.profile_limit, keys_only=keys_only
        )
        scope = "key columns" if keys_only else "all columns"
        print(f"  exact-profiled {len(done)} tables ({scope}, full row counts)")

    if conn is not None and args.usage:
        try:
            activity = usage.extract_query_activity(conn)
            usage.score_usage(catalog, activity)
            ranked = sum(1 for t in catalog.tables if t.query_count)
            print(f"  usage: scored {ranked} tables from {len(activity)} queries")
        except Exception as exc:  # noqa: BLE001 - usage needs extra perms; never fail the run
            print(f"  usage: skipped ({exc})")

    flagged = classify.annotate_pii(catalog)
    summary = classify.classify_catalog(catalog)
    print(f"  classified: {summary}")
    print(f"  PII columns flagged: {flagged}")

    assign = domains.infer_domains(catalog, strategy=args.domains)
    print(f"  domains: {len(set(assign.values()))} subject areas")

    findings = lint.lint_catalog(catalog)
    print(f"  health: {lint.summarize_lint(findings)}")

    score = readiness.compute_readiness(catalog, findings)
    print(f"  agentic readiness: {score['score']}/100 ({score['grade']} - {score['label']})")

    if args.path:
        try:
            src, dst = [p.strip() for p in args.path.split(",", 1)]
            print(f"  join path {src} -> {dst}:")
            print("    " + paths.path_to_text(paths.find_path(catalog, src, dst), src, dst).replace("\n", "\n    "))
        except ValueError:
            print("  --path expects 'schema.from_table,schema.to_table'")

    if conn is not None and args.describe:
        targets = profile.select_tables_to_profile(catalog, limit=args.describe_limit)
        ok = 0
        for t in targets:
            if semantic.describe_table(t, model=args.model, host=args.ollama_host):
                ok += 1
        print(f"  AI-described {ok}/{len(targets)} tables via {args.model}")

    json_path = _write(args.out, "catalog.json", render.to_json(catalog))
    md_path = _write(args.out, "catalog.md", render.to_markdown(catalog, findings=findings))
    mmd_path = _write(args.out, "erd.mmd", render.to_mermaid(catalog, max_tables=args.erd_tables))
    sql_path = _write(args.out, "relationships.sql", exports.to_sql_constraints(catalog))
    dbt_path = _write(args.out, "dbt_relationships.yml", exports.to_dbt_relationships(catalog))
    agent_path = _write(args.out, "agent_context.json", agentcontext.to_agent_json(catalog))
    html_path = _write(args.out, "catalog.html", htmlreport.render_html(catalog, findings))
    print(f"  wrote {json_path}")
    print(f"  wrote {md_path}")
    print(f"  wrote {mmd_path}")
    print(f"  wrote {sql_path}")
    print(f"  wrote {dbt_path}")
    print(f"  wrote {agent_path}")
    print(f"  wrote {html_path}  <- open this in a browser")


def _connect(args):
    from schema_scout import connect

    return connect.connect(
        conn_str=args.conn,
        server=args.server,
        database=args.database,
        user=args.user,
        password=args.password,
    )


def _add_common(p):
    p.add_argument("--out", default="out", help="output directory (default: out)")
    p.add_argument("--infer", action="store_true", default=True, help="infer undeclared FKs (default on)")
    p.add_argument("--no-infer", dest="infer", action="store_false")
    p.add_argument("--min-confidence", type=float, default=0.5)
    p.add_argument("--profile", action="store_true", help="sample-profile top tables")
    p.add_argument("--profile-limit", type=int, default=25)
    p.add_argument("--sample-size", type=int, default=50000)
    p.add_argument(
        "--exact-keys",
        action="store_true",
        help="exact (full-table) profile of key-like columns, to confirm PKs",
    )
    p.add_argument(
        "--exact",
        action="store_true",
        help="exact (full-table) profile of all aggregatable columns (heavy)",
    )
    p.add_argument("--validate", action="store_true", help="confirm inferred FKs by value inclusion")
    p.add_argument(
        "--usage",
        action="store_true",
        help="rank tables by query activity (Query Store / DMVs; needs permission)",
    )
    p.add_argument(
        "--path",
        metavar="FROM,TO",
        help="print the join path between two tables, e.g. dbo.orders,dbo.customers",
    )
    p.add_argument("--describe", action="store_true", help="AI descriptions via Ollama")
    p.add_argument("--describe-limit", type=int, default=25)
    p.add_argument("--model", default="qwen3:14b")
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--erd-tables", type=int, default=40, help="max tables in the ER diagram")
    p.add_argument(
        "--domains",
        choices=["auto", "prefix", "components"],
        default="auto",
        help="how to group tables into subject areas (default: auto)",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="schema-scout", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="extract + map a live SQL Server database")
    p_run.add_argument("--conn", help="full ODBC connection string (or set SCHEMA_SCOUT_CONN)")
    p_run.add_argument("--server")
    p_run.add_argument("--database")
    p_run.add_argument("--user")
    p_run.add_argument("--password")
    _add_common(p_run)

    p_demo = sub.add_parser("demo", help="run the pipeline on a synthetic catalog (no DB)")
    p_demo.add_argument("--large", action="store_true", help="use a bigger ~30-table, multi-domain schema")
    _add_common(p_demo)

    p_diff = sub.add_parser("diff", help="compare two saved catalog.json snapshots for drift")
    p_diff.add_argument("old", help="path to the earlier catalog.json")
    p_diff.add_argument("new", help="path to the later catalog.json")
    p_diff.add_argument("--json", action="store_true", help="emit the diff as JSON")

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        from schema_scout._demo import build_demo_catalog, build_large_demo_catalog

        print("schema-scout demo (synthetic catalog, no database)")
        catalog = build_large_demo_catalog() if args.large else build_demo_catalog()
        # demo has no live connection, so profiling/validate/describe/usage are skipped
        args.profile = False
        args.exact = False
        args.exact_keys = False
        args.validate = False
        args.describe = False
        args.usage = False
        _run_pipeline(catalog, None, args)
        return 0

    if args.cmd == "run":
        print("schema-scout: connecting...")
        conn = _connect(args)
        print("schema-scout: extracting structure...")
        catalog = extract.extract_catalog(conn)
        print(f"  {len(catalog.tables)} tables, {len(catalog.relationships)} declared FKs")
        _run_pipeline(catalog, conn, args)
        conn.close()
        return 0

    if args.cmd == "diff":
        import json as _json

        from schema_scout import catalog_io
        from schema_scout import diff as diffmod

        result = diffmod.diff_catalogs(
            catalog_io.load_catalog(args.old), catalog_io.load_catalog(args.new)
        )
        if args.json:
            print(_json.dumps(result, indent=2))
        else:
            print(diffmod.format_diff(result))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
