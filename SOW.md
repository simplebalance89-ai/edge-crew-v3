# Edge Crew v3 — Statement of Work

**Real-time sports betting intelligence pipeline: dual-path grading, Bayesian AI convergence, and curatorial filtering to surface 1-3 high-confidence plays per slate.**

---

## What It Does

Edge Crew v3 ingests live sports data and odds, then runs two independent grading pipelines simultaneously — a deterministic rule engine and a 5-model AI ensemble — and fuses the results using Bayesian weighting. A final gatekeeper model reads the full graded slate and returns the top 1-3 plays with trap flags. The system is designed for real-money betting decisions where a bad recommendation has direct financial cost. It operates across NBA, MLB, NFL, and soccer with sport-specific grading profiles.

---

## The Pipeline

1. **Data Ingestion** — Pulls ESPN team/player profiles, live odds from The Odds API, injury/news from RotoWire, and market sentiment from Kalshi. Assembled into a unified game object per matchup.

2. **Grading Engine** — Deterministic rule engine evaluates 50+ variables (rest days, travel, line movement, home/away splits, weather, injuries, public vs. sharp money). Outputs letter grades A+ through F per game. No AI involved — pure math and logic.

3. **AI Processor** — 5 models run in parallel, each with a distinct analytical persona to fight groupthink. Models: DeepSeek-R1-0528, Grok-4.1-fast-reasoning, Kimi-K2-Thinking, GPT-4o, Phi-4-reasoning. Each receives the same graded game object and returns a grade + confidence score + reasoning chain.

4. **Convergence** — Bayesian fusion layer precision-weights each AI output (weight = confidence²). Produces a convergence status per game: LOCK / ALIGNED / DIVERGENT / CONFLICT. LOCK requires both the rule engine and AI ensemble to agree with high confidence.

5. **Filter Mastermind** — Single gatekeeper model (Grok-4.1-fast-reasoning, temp=0.2) reads the full graded slate in one pass and returns the top 1-3 plays. Also flags trap games — high-public-action games that the math and AI don't support.

---

## Architecture

**Compute**
- FastAPI backend, async throughout, parallel model calls via `asyncio.gather`
- All AI calls use OpenAI-compatible v1 ChatCompletion format

**Azure Endpoints**
- Primary: `gce-personal-resource` (East US 2) — `https://gce-personal-resource.services.ai.azure.com/openai/v1/`
- Secondary: `peter-mna31gr3-swedencentral` — hosts Grok, DeepSeek, Kimi

**Models in Production**
| Model | Role |
|-------|------|
| DeepSeek-R1-0528 | Quant/value persona |
| Grok-4.1-fast-reasoning | Contrarian persona + Filter Mastermind |
| Kimi-K2-Thinking | Situational/narrative persona |
| GPT-4o | Baseline consensus persona |
| Phi-4-reasoning | Efficiency/line-value persona |
| Claude (via OpenRouter) | Backup / overflow |

---

## What Makes It Novel

- **Dual-path convergence** — Math and AI grade independently and simultaneously. Neither path gates the other. Final status is a function of agreement, not sequence.
- **Persona-differentiated ensemble** — Each model is prompted with a distinct analytical identity. Designed to produce genuine disagreement rather than correlated outputs.
- **Bayesian precision weighting** — AI confidence scores drive ensemble weight as confidence², not a flat average. A model that says "70% confident" is weighted less than one at "95% confident."
- **Convergence status taxonomy** — LOCK / ALIGNED / DIVERGENT / CONFLICT gives the downstream layer structured signal rather than a raw score.
- **Filter Mastermind** — One curatorial pass over the full slate rather than per-game thresholding. Reads the whole board, picks the best 1-3, and flags traps.

---

## Known Gaps

- **Hallucination risk** — AI models can cite statistics that don't exist. No source validation layer exists. A model can fabricate a player's injury status or recent performance trend.
- **Hard rules can be overridden** — "Peter Rules" profile restrictions (avoid certain game types, minimum grade thresholds) can be outvoted by AI ensemble consensus. The rule engine has no veto power over the Mastermind.
- **Cold-start latency** — First model call after idle hits Azure cold-start penalty of 500-800ms. No warm-ping or keepalive strategy in place.
- **Stale odds** — Odds are ingested once at slate load. Lines can move significantly by game time. No refresh loop.
- **No audit trail** — No record of why a play was surfaced or suppressed. Post-session review is manual and incomplete.
- **Silent outlier drops** — Ensemble outlier detection removes divergent model outputs without logging. Impossible to audit which models were discarded and why.

---

## Round Table Question

You are reviewing this system from scratch. Assume budget is not a constraint. Assume Azure is the cloud provider.

**How would you architect this system from the ground up today?**

Specifically address:
- Pipeline design (stages, sequence, data flow)
- Model selection and ensemble strategy
- How you would enforce hard rules that AI cannot override
- How you would handle cold-start latency
- How you would build the Filter Mastermind layer
- What you would do differently than what's described above

Be direct. Be opinionated. Tell us what's wrong with the current approach and how to fix it.
