OBJECTIVE
The attached documents establish that the filtration mastermind rebuild uses
a 5-stage pipeline (Ingestion → Intent → Retrieval → Grading → Gatekeeper)
on a normalized Postgres data model. What is NOT yet decided: which LLM
runs at which stage, whether to use an agent framework at all, and how
voice input fits the pipeline.

The current production system (attached reference, section 2 and 5) uses:
- GPT-4.1-mini for intent routing
- GPT-4.1 for reasoning/response generation
- Azure Whisper → GPT-4.1-mini extractor for voice
- Single-agent-with-tools pattern (one reasoning LLM reads tool outputs)

Andrew (the primary end user) says the current system is worse than the
last version he used. The reasoning-LLM hallucinates specs, voice context
is lost between turns, and the single-agent pattern makes it impossible to
enforce hard rules.

Your job: commit to the exact model selection and architecture decisions
below. No multi-option answers. No "it depends."

Unresolved questions:
1. What LLM runs Stage 1 (Ingestion validation)?
2. What LLM runs Stage 2 (Intent classification)?
3. What LLM runs Stage 3 (Retrieval ranking, if any LLM involvement)?
4. What LLMs make up the Stage 4 crowdsource ensemble (by role, not brand
   — another round will pick exact models)?
5. What LLM runs Stage 5 (Gatekeeper / response composition)?
6. Do we use an agent framework (Claude Agent SDK, OpenAI Assistants,
   LangGraph, custom) or write straight function calls with no framework?
7. Voice: does Whisper feed Stage 2 directly, or does it go through a
   separate voice-specific pipeline with different intents?
8. How do we fix Andrew's context loss problem across turns?

DO NOT:
- Recommend multiple options
- Hedge on framework choice
- Say "any good LLM will work"
- Write code

DO:
- Name specific model IDs (claude-opus-4-6, gpt-4.1, gpt-4.1-mini,
  claude-haiku-4-5, etc.) and justify each in one line
- Commit to agent framework OR no framework
- Commit to one voice pipeline shape
- Name the specific design choice that fixes Andrew's context loss

OUTPUT — return this exact shape:

# STACK ARCHITECTURE — FILTRATION MASTERMIND

## Model Selection (one model per stage, by ID)
STAGE_1_INGESTION: <model ID or "deterministic, no LLM"> — <one-line why>
STAGE_2_INTENT: <model ID> — <one-line why>
STAGE_3_RETRIEVAL: <model ID or "deterministic SQL, no LLM"> — <one-line why>
STAGE_4_GRADING_ROLES:
  - <role 1>: <model ID> — <why this model for this role>
  - <role 2>: <model ID> — <why>
  - <role 3>: <model ID> — <why>
  (minimum 3 roles, maximum 7)
STAGE_5_GATEKEEPER: <model ID or "rule engine in code"> — <one-line why>
STAGE_5_RESPONSE_COMPOSITION: <model ID> — <one-line why>

## Agent Framework Decision
CHOICE: <Claude Agent SDK | OpenAI Assistants | LangGraph | custom | no framework>
REASON: <one line>
WHAT_IT_REPLACES_IN_CURRENT_CODE: <one line>

## Voice Pipeline
WHISPER_ENDPOINT: <Azure Whisper | OpenAI Whisper | other>
EXTRACTOR: <model ID>
PATH_INTO_PIPELINE: <does voice transcript feed Stage 2 intent directly,
                     or does it go through a separate voice handler first>
CONTEXT_RETENTION_MECHANISM: <exactly how we keep multi-turn context —
                              conversation memory? session state in Postgres?
                              agent thread? be concrete>

## Why This Fixes Andrew's Context Loss
ROOT_CAUSE: <one sentence — why context is being lost today>
FIX: <one sentence — the specific design choice that eliminates it>

## Why This Fixes Spec Hallucination
ROOT_CAUSE: <one sentence>
FIX: <one sentence>

## Cost Budget (rough)
PER_QUERY_COST_USD: <estimate based on your model choices>
DOMINANT_COST_DRIVER: <which stage eats the most tokens>

## Latency Budget (p95, ms, measured end-to-end)
VOICE_PATH: <ms>
TEXT_PATH: <ms>

## One-Sentence Rationale for the Whole Stack
<Why this specific stack, in one sentence, as if pitching to Andrew.>

RULES
- Name models by ID. No "a strong open-source model."
- If you pick a framework, name the specific classes/functions you'd use.
- If you say "no framework," name the HTTP client and the function-call
  shape instead.
- Voice and text must use the SAME intent classifier — no parallel intent
  systems.
