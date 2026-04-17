"""
Edge Crew v3 — Filter Mastermind
AI-powered filter evaluation. Sends a slate of graded games to a single
Azure model and asks it to identify the highest-confidence plays.
"""

import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("edge-crew-v3")

# ─── Azure credentials (GCE primary) ─────────────────────────────────────────

GCE_ENDPOINT = os.environ.get(
    "GCE_ENDPOINT",
    "https://gce-personal-resource.services.ai.azure.com/openai/v1/"
)
GCE_KEY = os.environ.get("AZURE_GCE_KEY", "") or os.environ.get("AZURE_OPENAI_KEY", "")

MASTERMIND_MODEL = os.environ.get("MASTERMIND_MODEL", "grok-4-1-fast-reasoning")
MASTERMIND_TIMEOUT = int(os.environ.get("MASTERMIND_TIMEOUT", "90"))


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _build_mastermind_prompt(games: list) -> str:
    """Build the filter prompt from a list of graded games."""
    lines = []
    for g in games:
        game_id = g.get("game_id", "unknown")
        matchup  = g.get("matchup", game_id)
        grade    = g.get("grade", "?")
        score    = g.get("score", 0)
        pick     = g.get("pick", "")
        thesis   = g.get("thesis", "")
        lines.append(f"- {matchup} | Grade: {grade} ({score:.1f}) | Pick: {pick} | Thesis: {thesis}")

    slate_text = "\n".join(lines) if lines else "(no games)"

    return f"""You are the Filter Mastermind for a sports betting AI system.
Below is today's graded slate. Your job is to identify the 1-3 highest-confidence plays.

GRADED SLATE:
{slate_text}

RULES:
1. Only surface plays with genuine edge — do not pad the list.
2. For each selected play, explain WHY it clears the bar (data edge, line value, convergence).
3. Flag any plays that look like traps despite a high grade.
4. Return your answer as JSON with this exact shape:

{{
  "top_plays": [
    {{
      "game_id": "<game_id>",
      "pick": "<side or total>",
      "confidence": "<A+|A|A-|B+>",
      "reason": "<1-2 sentence rationale>"
    }}
  ],
  "traps": ["<game_id>", ...],
  "summary": "<1 sentence overall slate read>"
}}
"""


# ─── Azure call ───────────────────────────────────────────────────────────────

async def _call_mastermind(prompt: str) -> Optional[str]:
    url = f"{GCE_ENDPOINT.rstrip('/')}/chat/completions"
    headers = {
        "api-key": GCE_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "model": MASTERMIND_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    try:
        async with httpx.AsyncClient(timeout=MASTERMIND_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("Filter Mastermind call failed: %s", exc)
        return None


# ─── Response parser ──────────────────────────────────────────────────────────

def _parse_mastermind_response(raw: str) -> dict:
    """Extract JSON from the model response."""
    try:
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as exc:
        logger.warning("Could not parse Mastermind response: %s", exc)
        return {"top_plays": [], "traps": [], "summary": raw[:200], "parse_error": True}


# ─── Public entry point ───────────────────────────────────────────────────────

async def run_filter_mastermind(games: list) -> dict:
    """
    Pass a list of graded game dicts, get back the Mastermind's top picks.

    Each game dict should have at minimum:
        game_id, matchup, grade, score, pick, thesis
    """
    if not games:
        return {"top_plays": [], "traps": [], "summary": "Empty slate."}

    prompt = _build_mastermind_prompt(games)
    logger.info("Filter Mastermind: evaluating %d games with %s", len(games), MASTERMIND_MODEL)

    raw = await _call_mastermind(prompt)
    if not raw:
        return {"top_plays": [], "traps": [], "summary": "Mastermind call failed.", "error": True}

    result = _parse_mastermind_response(raw)
    logger.info("Filter Mastermind: %d top plays identified", len(result.get("top_plays", [])))
    return result
