# Contributing

Thanks for taking a look. Bug reports, ideas, and pull requests are all
welcome.

## Setup

```bash
git clone https://github.com/Pawansingh3889/schema-scout
cd schema-scout
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"
python -m pytest
```

You don't need a database to develop. Run the synthetic demo:

```bash
python -m schema_scout.cli demo --large
```

## How the code is laid out

Each stage is its own module under `schema_scout/`, and the logic that doesn't
need a database is kept pure so it can be tested without one:

- `extract.py`, `connect.py`, `profile.py`, `usage.py` — touch the database
- `relationships.py`, `classify.py`, `domains.py`, `lint.py`, `paths.py`,
  `exports.py`, `render.py`, `htmlreport.py` — pure functions over the
  in-memory catalog (`model.py`)
- `_demo.py` — synthetic catalogs used by the demo and the tests

If you can write a feature as a pure function over the catalog, please do, it
keeps it testable.

## Before you open a PR

- Run the tests: `python -m pytest`
- Keep the diff focused and the commit messages plain and descriptive
- Add a test for any new pure logic (see `tests/` for the pattern)

## Good first issues

Look for the `good first issue` label. Small, self-contained things like a new
health check, a new PII pattern, or a render tweak are a good place to start.
