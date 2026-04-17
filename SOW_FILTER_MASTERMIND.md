# SOW: Filter Mastermind Module
**Edge Crew v3 — Standalone Architecture Brief**

---

## What Is Filter Mastermind

Filter Mastermind is the final curatorial AI layer in the Edge Crew v3 pipeline. After 20–40 games have been graded by five independent AI models — each producing a grade (A+ to F), a numeric score, a pick, and a thesis — Filter Mastermind reads the full slate holistically and identifies the 1–3 highest-conviction plays worth acting on. It is not a grader. It does not re-analyze individual games. Its sole job is curation: given everything the pipeline has already produced, which plays represent genuine edge, and which should be passed over regardless of their individual grade.

---

## Current Implementation

- Single Azure OpenAI model call (GPT-4o or Claude Sonnet)
- Temperature: 0.2
- Input: full graded slate as JSON
- Output schema: `{ top_plays: [...], traps: [...], summary: string }`
- No system prompt tuning beyond basic role assignment
- Runs once per slate, stateless

---

## Current Limitations

- **Single model:** one AI's opinion with no cross-validation or dissent detection
- **No memory:** each slate is evaluated in isolation — no awareness of recent record, hot/cold models, or sport-specific drift
- **No bankroll context:** treats a $50 unit and a $500 unit identically; no Kelly-style sizing signals
- **No calibration:** no mechanism to tune aggression — it may return 3 plays on a 4-game slate or 1 play on a 40-game slate with no consistency
- **No line movement awareness:** a sharp line move that invalidates a thesis is invisible to the mastermind
- **No trap detection logic:** a game can grade A+ from all five models and still be a coordinated public fade — the current layer has no structural defense against this

---

## Round Table Question

You are designing a Filter Mastermind from scratch. It sits at the end of a sports betting analytics pipeline. It receives a full graded slate (20–40 games, each with a grade A+ to F, a score, a pick, and a thesis from 5 different AI models).

**Its job: identify the 1–3 highest-conviction plays from the slate.**

How would you build this?

Specifically address:

- **Single model vs. multi-model approach** — is one strong model enough, or do you run the mastermind itself as an ensemble? If ensemble, how do you resolve disagreement?
- **What context should be injected** — historical performance by sport/model/grade tier? Current bankroll and unit size? Line movement since initial grade? Weather or injury flags? Where do you draw the line to avoid noise?
- **How you would prevent overconfidence** — the mastermind has access to strong grades from multiple models; what structurally stops it from rubber-stamping everything above a threshold?
- **How you would detect trap games** — a game where all five models agree but the line has moved against the pick, or where public money is suspiciously aligned. How does the mastermind flag or kill these?
- **Calibration** — how do you tune it so it returns the right number of plays? Not too conservative (1 play every 3 slates), not too aggressive (6 plays on a Tuesday NBA card). Is this a prompt parameter, a post-processing rule, or something else?
- **Output schema** — what fields does a top play entry need beyond pick + grade? Confidence interval? Reasoning chain? Dissent flags? Keep it usable, not academic.
- **Memory of previous slates** — should the mastermind know its own recent record? The record of each upstream model by sport? Or does memory introduce recency bias that hurts more than it helps?

Be direct. Be opinionated. Don't describe the problem — prescribe the solution. If you'd build it differently depending on bankroll size or sport, say so.
