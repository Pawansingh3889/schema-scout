# PII classification and anonymization: design

Status: design, not yet built. This captures the intended shape of a PII
discovery and anonymization capability that extends schema-scout's existing
structural analysis and drift detection.

## The principle everything rests on

PII is not a property of a value. It is a property of a value in a context.
"Rose" is neither personal nor safe on its own. It depends on what column it
sits in, what it links to, and whether it can single out a living person. Any
tool that decides PII by matching values against a name dictionary is built on
the wrong primitive. The clean proof is a name that is also a common word:
a product `variety` column and a `surname` column can hold the identical set of
values and yet one is a catalog and the other is personal data. So the
unit of classification is the column, not the value, and the discriminating
signals come from structure and distribution, not from the characters in a cell.

The whole capability is one loop: **discover, then a human confirms, then
enforce.** Discovery proposes classifications with reasons and a confidence
score. A human resolves the ambiguous ones once. The confirmed decision is
written to a catalog and reused, never re-guessed. Enforcement reads the
catalog at query time.

## Discovery: scoring a column

Signals, in order of trust:

1. Structural. Column name patterns (`email`, `dob`, `postcode`, `surname`),
   data type and constraints, and foreign-key role. A column that joins to a
   person table is a person pointer regardless of its own values. schema-scout
   already infers undeclared foreign keys, so this signal is in reach.
2. Contextual. The table's other columns disambiguate. A column beside `email`,
   `phone`, and `address` is a name column even if every value is a common word;
   the same values beside `price`, `weight`, and `sku` are a product.
3. Distribution. Used only as a tiebreaker, never as the primary decision.

The structural and contextual signals dominate. Distribution breaks ties.

## The distribution math

The discriminator between a bounded vocabulary (products, statuses) and an open
personal namespace (names, emails) is not the number of distinct values. It is
the rate at which new distinct values keep arriving as you scan. Distinct count
is sample-size fragile. Arrival rate is not.

Let `n` be rows sampled, `d` distinct values, and `count(v)` the value frequencies.

- Distinct ratio `d / n`. Near 1.0 flags a unique identifier (key, email). Weak
  for the person-versus-product call because it moves with `n`.
- Saturation. Record distinct count at the halfway point and the end, `D(n/2)`
  and `D(n)`. Then `r = D(n) / D(n/2)` and the Heaps exponent `beta = log2(r)`.
  `r` near 1.0 (`beta` near 0) means no new values in the second half: a bounded
  vocabulary. `r` around 1.3 to 1.6 means new values keep arriving: an open
  namespace. This is the primary distribution signal.
- Singleton ratio `f1 / d`, where `f1` is the count of values seen exactly once.
  Near 0 for a controlled vocabulary, high for personal names. The Good-Turing
  estimate `f1 / n` approximates the chance the next row holds an unseen value.
- Normalized entropy `H / log2(d)`. Measures evenness, not cardinality. Its job
  is to gate out skewed low-cardinality categoricals (status, grade), not to
  make the name-versus-product call.

The rule that kills the false positive: weight any name-dictionary hit by
`beta`. In a saturated low-cardinality column the dictionary match is worthless
and gets discounted toward zero; in a high-arrival-rate column it is trusted.
Two columns with identical values and a near-identical dictionary hit rate
separate cleanly because one has `beta` near 0.03 and the other near 0.43.

Fuse the signals with a gated cascade, not a weighted sum, so a strong
structural signal is never outvoted by three weak distribution signals. Output
per column is a record: proposed class, confidence, the contributing signals,
and the sample evidence. The reasons are not optional. A reviewer needs to see
"flagged because 38 percent surname-dictionary match" to override a false
positive in one step.

Traps to respect: sample randomly, never sequentially, or a table clustered by
one column shows false saturation. A tiny contamination in the tail (a handful
of real names in a product column) will still score as safe. And a small sample
inflates `beta`, so record `n` in the evidence.

## The quasi-identifier pass

Per-column classification misses the mosaic effect: columns that are each
harmless can be jointly identifying. Postcode, date of birth, and sex are each
"not a direct identifier," yet together they are close to a fingerprint for most
of a population. This is a table-level property that column-level analysis
cannot see, and almost nothing on the market checks for it.

The measure is k-anonymity. Group the rows by the quasi-identifier columns; each
group is an equivalence class; `k` is the smallest class size. `k` of 1 means at
least one person is unique on those columns.

```sql
SELECT MIN(cnt) AS k,
       SUM(CASE WHEN cnt = 1 THEN 1 ELSE 0 END) AS unique_rows
FROM (SELECT postcode, dob, sex, COUNT(*) AS cnt
      FROM t GROUP BY postcode, dob, sex) g;
```

Which columns are quasi-identifiers is a human judgment (are they knowable about
a person from outside the data?), seeded by the discovery heuristics and confirmed
once, exactly like the per-column tags. The threat model is documented alongside
the choice, because `k` is only meaningful relative to what an attacker is
assumed to know.

Do not enumerate all column subsets; that is the NP-hard optimization. Use
monotonicity: adding a quasi-identifier can only lower or hold `k`, so the full
set is the worst case. Measure it first. If it passes the target, every subset
passes too.

Report three numbers, not one: the minimum `k`, the percentage of rows in
classes below the target (the population at risk, the number a data owner acts
on), and the count of unique rows. Compute `k` on the full table or the exact
released set, never a sample, and bin continuous columns first or every row looks
unique.

## Remediation: greedy generalization

When the quasi-identifier set fails the target, coarsen columns until `k` rises.
Each quasi-identifier gets an ordered ladder of generalization levels, each level
a SQL expression, terminating in full suppression:

```
postcode: SW1A 1AA  ->  SW1A 1  ->  SW1A  ->  SW1  ->  *
dob:      exact    ->  year   ->  5yr band  ->  *
```

The search is greedy, not optimal. State is the vector of current levels. A move
bumps one column up one level. At each step, try bumping each column and take the
one with the best ratio of k gained to information lost, until `k` reaches the
target. Information loss can start as a simple average of normalized ladder
levels and upgrade to discernibility (`sum of squared class sizes`) later. The
output is the ordered sequence of moves, which reads as a plan: generalize
postcode to district (k rises 1 to 6, clears 89 percent of at-risk rows), then
bin date of birth to five-year bands (k rises to 22, clears the rest).

Prefer suppressing a small residual of stubborn unique rows over coarsening a
whole column another level, capped by a suppression budget. Beyond the budget,
escalate to a human. State the utility trade in the plan's final line so a data
owner can decide, which is the governance job.

Greedy can miss a better joint move and its quality is capped by the ladder
granularity, so ladder design is where the care goes. Note these limits rather
than hide them. Mondrian-style multidimensional partitioning is the literature
baseline and a roadmap item, not a v1.

## Enforcement

Static generalization alone is not enforcement. A view where postcode is coarsened
to district can still be narrowed back to one person by a filter on district, age
band, and sex. Real enforcement is two layers:

1. Compile-time generalization. Because the agent never writes raw SQL and the
   query is compiled from a semantic layer, generalization is the expression the
   compiler emits, chosen by the caller's role. A low-privilege role cannot
   request the raw column because the compiler will not emit it. This is stronger
   than database-native masking, which sits behind an interface a clever query
   can still probe.
2. Result-time k-floor. Before results return, refuse or suppress any output
   group whose size falls below `k`. The check is against the result set, not the
   base table, because the filter is part of the query. This is the layer that
   closes the hole static generalization leaves, and it can only live at the
   gateway that sees the compiled query.

Policy is data, not code: a versioned, reviewed artifact naming the quasi-identifiers,
the threat model, the target `k`, the generalization ladders, and the per-role
generalization state and k-floor. Roles map to clearance: an auditor sees raw, an
analyst sees the greedy plan's state, a read-only agent sees the coarsest state
with a hard result floor.

The tools compose. A role gate resolves the caller to a policy. The semantic layer
emits the generalized expressions and injects the k-floor. A masking pass covers
residual identifier columns in result rows. An append-only audit log records the
enforced state per query: role, policy version, generalization state, k-floor,
groups suppressed, and the snapshot the policy was computed against.

Drift is the quiet failure. A k guarantee is computed against a snapshot; new rows
can push a class below the target with no error raised. Two defenses: the
result-time k-floor makes drift safe by default because it checks current data,
and schema-scout's drift detection re-runs the k computation on a schedule and
flags when live `k` falls under the policy target.

## Scope for a first version

Discovery with the gated cascade and reasons. The quasi-identifier pass with the
three-number report. Greedy generalization with a simple loss metric and a
suppression budget. Enforcement as compile-time generalization plus a result-time
k-floor plus the audit record. Leave for later: learned scoring calibrated on
confirmed labels, l-diversity and t-closeness, Mondrian partitioning, and a
standalone drift scheduler.

The through-line: measure the re-identification risk, generate the fix as a
reviewable per-role policy, enforce it at query-compile and result time, and prove
in a tamper-evident log which policy governed every query. Measure, fix, enforce,
prove.
