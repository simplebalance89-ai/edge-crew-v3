OBJECTIVE
A prior Round Table round (Round 6, attached as reference) converged on a
normalized Postgres schema and a crowdsource grading stage for the filtration
mastermind rebuild, but left four architectural splits unresolved plus two
real bugs that only one model each caught.

Your job: commit to a single answer on every split below. No "it depends."
No multiple options. Pick one, justify in one line, move on.

THE FOUR SPLITS

1. activity_state location
   - Option A: Separate `product_state` table refreshed nightly.
     Pro: isolates volatile inventory from stable product master.
     Con: 23-hour stale activity state during daytime inventory changes.
   - Option B: Column on `products` table, updated with inventory refresh.
     Pro: no join cost on retrieval.
     Con: bloats the product master with volatile state.
   - Option C: Separate table but trigger-driven on inventory refresh,
     not nightly batch.

2. Crowdsource ensemble size
   - 3 models: cheapest, lowest latency, risk of tie deadlock.
   - 5 models: plurality vote in Round 6 (8 models backed this).
   - 7 models: minority vote (6 models backed this).
   - Cost reality: 7 models × 50 queries/day ≈ $35/day inference vs
     $5/day single-model. That's a $10,950/year delta.

3. Consensus algorithm
   - Majority vote: simple, deadlocks on 2-2-1 splits.
   - Weighted average: requires per-model weights, hard to tune.
   - Condorcet + gatekeeper override (Mistral's pick): deterministic,
     lets rule engine veto.
   - Trimmed mean (drop high + low, average the middle, Kimi K2.5's pick):
     kills outliers, needs ≥5 models.

4. Stage 4 latency budget (p95, ms)
   - 1200ms: risky under Azure throttling.
   - 1500ms: called "optimistic" by the model that proposed it.
   - 2000ms: plurality-reasonable.
   - 2500ms: Kimi's pick, leaves 1.5s for rest of pipeline.
   - 2800ms: DeepSeek V3's pick — intentionally tight to force upstream optimization.
   Ground truth: Azure OpenAI cold starts can eat 500-800ms on a tool
   that doesn't run 24/7. Sales-floor p95 end-to-end budget is 4 seconds.

THE TWO BUGS

BUG A: Material name normalization.
   Kimi K2.5 caught this in Round 6: "If P21 sends 'Polypropylene' and your
   static file has 'PP', the chemical_compatibility join fails and you return
   'unknown compatibility' when you should have a hit." Real products: 'PP'
   vs 'Polypropylene' vs 'Polypropylen', '316 SS' vs '316L SS' vs 'Stainless
   Steel 316L', 'PTFE' vs 'Teflon'.
   Commit to one normalization strategy.

BUG B: Coated media edge case.
   DeepSeek R1 caught this: "Pall HC9600 is nickel-coated PTFE. If
   chemical_compatibility is keyed on media_type alone, you return 'PTFE
   resists acids' — but the nickel coating may not. Products exist where
   the coating is the failure surface, not the base media."
   Commit to how the schema handles coated/composite media.

DO NOT:
- Offer multiple options
- Say "it depends on scale" — assume 50 queries/day, 4s p95
- Defer decisions to "a later round"
- Write code

DO:
- Pick one answer per question
- Cite which Round 6 model's reasoning you're siding with when relevant
- State your assumption in one line if the reference doc is silent

OUTPUT — return this exact shape:

# SPLIT RESOLUTIONS — FILTRATION MASTERMIND

## Split 1 — activity_state Location
CHOICE: <A separate product_state nightly | B column on products | C trigger-driven table>
REASON: <one line>
FAILURE_MODE_WE_ACCEPT: <what we give up by making this choice>

## Split 2 — Ensemble Size
CHOICE: <3 | 5 | 7>
REASON: <one line, must address cost>
COST_PER_YEAR: <$X based on 50 queries/day>

## Split 3 — Consensus Algorithm
CHOICE: <majority | weighted | condorcet+override | trimmed mean | other>
FORMULA: <one line>
TIE_BREAKER: <one line>
MINIMUM_AGREEMENT: <N of M must agree or reject>

## Split 4 — Stage 4 Latency Budget
P95_MS: <number>
REMAINING_BUDGET_FOR_OTHER_STAGES: <ms, out of 4000ms total>
HOW_WE_HIT_IT: <parallelism, caching, warm pool — one line>

## Bug A — Material Name Normalization
STRATEGY: <canonical table | fuzzy match | LLM normalization at ingestion | other>
WHERE_IT_RUNS: <ingestion | query time | both>
CANONICAL_SOURCE: <which file/table holds the master material name list>
HOW_WE_HANDLE_UNKNOWN_MATERIAL: <one line>

## Bug B — Coated/Composite Media
SCHEMA_CHANGE: <one-line description — e.g. "add media_coating column with FK to coatings table">
JOIN_BEHAVIOR: <how chemical_compatibility is queried for coated media>
CONSERVATIVE_DEFAULT: <if coating compatibility is unknown, what does the system return>

## One-Paragraph Rationale
<Why these six choices fit together as a single coherent design. Max 4 sentences.>

RULES
- One answer per question. No alternatives.
- Every decision must be defensible in one line.
- If you disagree with the Round 6 plurality on any split, say why in the REASON line.
