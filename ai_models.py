"""
Edge Crew v3 — AI Model Crowdsource
Calls multiple AI models for independent game analysis with reasoning.
Each model returns a grade + thesis (WHY they graded it that way).
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("edge-crew-v3")

# ─── Azure AI Services (Sweden Central — Grok, DeepSeek, Kimi all here) ──────

AI_SERVICES_ENDPOINT = os.environ.get(
    "AI_SERVICES_ENDPOINT",
    "https://peter-mna31gr3-swedencentral.services.ai.azure.com/openai/v1/"
)
AI_SERVICES_KEY = os.environ.get("AZURE_SWEDEN_KEY", "") or os.environ.get("AZURE_AI_KEY", "")

# GCE Personal Resource (fallback)
GCE_ENDPOINT = os.environ.get(
    "GCE_ENDPOINT",
    "https://gce-personal-resource.services.ai.azure.com/openai/v1/"
)
GCE_KEY = os.environ.get("AZURE_GCE_KEY", "") or os.environ.get("AZURE_OPENAI_KEY", "")

# Anthropic (Claude)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Google Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GRADE_MAP = {
    "A+": 9.5, "A": 8.5, "A-": 7.5, "B+": 7.0, "B": 6.5, "B-": 6.0,
    "C+": 5.5, "C": 5.0, "D": 3.5, "F": 2.0,
}

SCORE_TO_GRADE = [
    (8.5, "A+"), (7.8, "A"), (7.0, "A-"), (6.5, "B+"), (6.0, "B"),
    (5.5, "B-"), (5.0, "C+"), (4.0, "C"), (3.0, "D"), (0.0, "F"),
]


def _score_to_grade(score: float) -> str:
    for threshold, grade in SCORE_TO_GRADE:
        if score >= threshold:
            return grade
    return "F"


# ─── Model Registry ───────────────────────────────────────────────────────────

AI_MODELS = [
    {
        "name": "DeepSeek-R1-0528",
        "display": "DeepSeek R1",
        "endpoint": "ai_services",
        "timeout": 60,
        "personality": "analytical, data-driven, finds hidden edges in matchup stats",
    },
    {
        "name": "grok-4-1-fast-reasoning",
        "display": "Grok 4.1",
        "endpoint": "ai_services",
        "timeout": 60,
        "personality": "sharp contrarian, challenges consensus, sniffs out trap games",
    },
    {
        "name": "Kimi-K2-Thinking",
        "display": "Kimi K2 Thinking",
        "endpoint": "ai_services",
        "timeout": 60,
        "personality": "scout profiler, evaluates tactical DNA and structural edges",
    },
    {
        "name": "gpt-5.4-nano",
        "display": "GPT 5.4 Nano",
        "endpoint": "azure_openai",
        "timeout": 45,
        "personality": "balanced consensus builder, weighs all factors equally, finds the middle ground",
    },
    {
        "name": "claude-opus-4-6",
        "display": "Claude Opus 4.6",
        "endpoint": "ai_services",
        "timeout": 60,
        "personality": "deep strategic thinker, momentum and narrative focus, contrarian on big spreads",
    },
    {
        "name": "Phi-4-reasoning",
        "display": "Phi-4 Reasoning",
        "endpoint": "gce",
        "timeout": 45,
        "personality": "chain-of-thought reasoner, digs into process disagreements, sharp on thin edges",
    },
    {
        "name": "qwen3-32b",
        "display": "Qwen 3-32B",
        "endpoint": "ai_services",
        "timeout": 60,
        "personality": "pattern recognition powerhouse, record differentials and historical trends, aggressive on mismatches",
    },
]


def _build_game_prompt(game: dict, model_personality: str) -> str:
    """Build the analysis prompt for a single game."""
    home = game.get("homeTeam", "?")
    away = game.get("awayTeam", "?")
    sport = game.get("sport", "?")
    odds = game.get("odds", {})
    hp = game.get("home_profile", {})
    ap = game.get("away_profile", {})

    # Build context block
    lines = [
        f"MATCHUP: {away} @ {home}",
        f"SPORT: {sport}",
    ]

    if odds:
        spread = odds.get("spread", 0)
        total = odds.get("total", 0)
        ml_h = odds.get("mlHome", 0)
        ml_a = odds.get("mlAway", 0)
        lines.append(f"ODDS: Spread {spread:+.1f} | O/U {total} | ML {ml_a}/{ml_h}")

    for tag, prof in [("HOME", hp), ("AWAY", ap)]:
        parts = []
        if prof.get("record"): parts.append(f"Record: {prof['record']}")
        if prof.get("L5"): parts.append(f"L5: {prof['L5']}")
        if prof.get("streak"): parts.append(f"Streak: {prof['streak']}")
        if prof.get("ppg_L5"): parts.append(f"PPG: {prof['ppg_L5']}")
        if prof.get("opp_ppg_L5"): parts.append(f"OPP PPG: {prof['opp_ppg_L5']}")
        if prof.get("rest_days") is not None: parts.append(f"Rest: {prof['rest_days']}d")
        if prof.get("is_b2b"): parts.append("B2B")
        if prof.get("home_record"): parts.append(f"Home: {prof['home_record']}")
        if prof.get("away_record"): parts.append(f"Away: {prof['away_record']}")
        if parts:
            lines.append(f"{tag}: {' | '.join(parts)}")

    context = "\n".join(lines)

    return f"""You are an elite sports analyst. Your personality: {model_personality}.

Grade this game on a 1-10 scale and explain WHY in 2-3 sentences.

{context}

Return ONLY valid JSON:
{{"grade": "A-", "score": 7.2, "confidence": 82, "pick": "team name", "thesis": "2-3 sentences explaining WHY you graded it this way — what's the edge or concern?", "key_factors": ["factor1", "factor2", "factor3"]}}

Be specific. Name players, cite records, reference the odds. Don't hedge — take a side."""


# Hardcoded knowledge — NHL goalie tier dicts come from grade_engine. Pitcher
# tier was killed: there is no name-based ace list anymore. Pitchers are
# graded inline from real ERA/WHIP/K9 in the prompt block below.
from grade_engine import (  # type: ignore
    ELITE_NHL_GOALIES as _ENG,
    GOOD_NHL_GOALIES as _GNG,
)

_BATCH_HITTER_PARKS = {
    "Colorado Rockies", "Texas Rangers", "Boston Red Sox",
    "Cincinnati Reds", "Philadelphia Phillies", "Arizona Diamondbacks",
}
_BATCH_ELITE_GOALIES = {str(k).lower() for k in _ENG}
_BATCH_GOOD_GOALIES = {str(k).lower() for k in _GNG}


def _sp_stats_inline(sp: dict) -> str:
    """Render a starting pitcher's real stats for the batch prompt. No tier
    label — the LLM grades the pitcher from the actual ERA/WHIP/K9/IP."""
    if not isinstance(sp, dict):
        return ""
    parts = []
    if sp.get("era") is not None:
        parts.append(f"{sp['era']} ERA")
    if sp.get("whip") is not None:
        parts.append(f"{sp['whip']} WHIP")
    if sp.get("k9") is not None:
        parts.append(f"{sp['k9']} K/9")
    if sp.get("ip") is not None:
        parts.append(f"{sp['ip']} IP")
    return f" [{', '.join(parts)}]" if parts else " [no stats]"


def _batch_goalie_tier(name: str) -> str:
    if not name or name == "TBD":
        return "UNKNOWN"
    parts = name.strip().lower().split()
    last = parts[-1] if parts else ""
    if last in _BATCH_ELITE_GOALIES:
        return "ELITE"
    if last in _BATCH_GOOD_GOALIES:
        return "GOOD"
    return "AVERAGE"


def _build_batch_prompt(games: list, model_personality: str, sport: str = "") -> str:
    """Build prompt for batch grading multiple games."""
    sport_u = (sport or "").upper()
    game_blocks = []
    for i, game in enumerate(games):
        home = game.get("homeTeam", "?")
        away = game.get("awayTeam", "?")
        odds = game.get("odds", {})
        hp = game.get("home_profile", {})
        ap = game.get("away_profile", {})
        # Per-game sport fallback in case caller passes "" (mixed batch).
        g_sport = (game.get("sport") or sport_u).upper()

        lines = [f"GAME {i+1}: {away} @ {home}"]
        if odds:
            lines.append(f"  Spread: {odds.get('spread', 0):+.1f} | O/U: {odds.get('total', 0)} | ML: {odds.get('mlAway', 0)}/{odds.get('mlHome', 0)}")

        for tag, prof in [("HOME", hp), ("AWAY", ap)]:
            parts = []
            if prof.get("record"): parts.append(f"{prof['record']}")
            if prof.get("L5"): parts.append(f"L5:{prof['L5']}")
            if prof.get("streak"): parts.append(f"Streak:{prof['streak']}")
            if prof.get("ppg_L5"): parts.append(f"PPG:{prof['ppg_L5']}")
            if prof.get("rest_days") is not None: parts.append(f"Rest:{prof['rest_days']}d")
            if prof.get("is_b2b"): parts.append("B2B")
            if parts:
                lines.append(f"  {tag}: {' | '.join(parts)}")

        # MLB: pitcher tiers + park factor.
        if g_sport == "MLB":
            h_sp_d = hp.get("starting_pitcher") or {}
            a_sp_d = ap.get("starting_pitcher") or {}
            h_sp = h_sp_d.get("name", "TBD")
            a_sp = a_sp_d.get("name", "TBD")
            lines.append(
                f"  PITCHERS: {away} {a_sp}{_sp_stats_inline(a_sp_d)} | "
                f"{home} {h_sp}{_sp_stats_inline(h_sp_d)}"
            )
            if home in _BATCH_HITTER_PARKS:
                lines.append("  PARK: hitter-friendly (boost offense, hurt pitchers)")

        # NHL: starting goalies + tiers. Data layer often leaves this TBD —
        # TODO: populate starting_goalie in profile dicts (next session).
        if g_sport == "NHL":
            h_g = (hp.get("starting_goalie") or {}).get("name", "TBD")
            a_g = (ap.get("starting_goalie") or {}).get("name", "TBD")
            lines.append(
                f"  GOALIES: {away} {a_g} ({_batch_goalie_tier(a_g)}) | "
                f"{home} {h_g} ({_batch_goalie_tier(h_g)})"
            )

        game_blocks.append("\n".join(lines))

    games_text = "\n\n".join(game_blocks)

    return f"""You are an elite sports analyst. Your personality: {model_personality}.

Grade EACH game below on a 1-10 scale. For each game, explain WHY in 2-3 sentences.

{games_text}

Return ONLY valid JSON:
{{"games": [
  {{"game_index": 1, "grade": "A-", "score": 7.2, "confidence": 82, "pick": "team name", "thesis": "2-3 sentences explaining WHY", "key_factors": ["factor1", "factor2"]}}
]}}

Be specific and decisive. Name teams, cite stats, reference odds. Take a side — no hedging."""


AZURE_OPENAI_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    "https://peterwilson.openai.azure.com/openai/deployments/"
)
AZURE_OPENAI_KEY = AI_SERVICES_KEY  # Same Sweden key works for peterwilson endpoint


async def _call_azure_model(model_name: str, prompt: str, timeout: int = 60, endpoint_type: str = "ai_services") -> Optional[str]:
    """Call an Azure AI model, routing to the correct endpoint."""
    if endpoint_type == "gce":
        key = GCE_KEY
        endpoint = GCE_ENDPOINT
    elif endpoint_type == "azure_openai":
        key = AI_SERVICES_KEY or GCE_KEY
        endpoint = f"{AZURE_OPENAI_ENDPOINT}{model_name}/chat/completions?api-version=2025-01-01-preview"
    else:  # ai_services (default)
        key = AI_SERVICES_KEY or GCE_KEY
        endpoint = AI_SERVICES_ENDPOINT

    if not key:
        return None

    try:
        if endpoint_type == "azure_openai":
            url = endpoint
        else:
            url = f"{endpoint}chat/completions"

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers={"api-key": key, "Content-Type": "application/json"},
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens": 4000,
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                logger.warning(f"[AI] {model_name}: HTTP {resp.status_code} — {resp.text[:200]}")
                return None
    except Exception as e:
        logger.warning(f"[AI] {model_name}: {e}")
        return None


async def _call_anthropic(prompt: str, timeout: int = 60) -> Optional[str]:
    """Call Claude via Anthropic API."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 4000,
                    "temperature": 0.4,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("content", [{}])[0].get("text", "")
            else:
                logger.warning(f"[AI] Claude: HTTP {resp.status_code}")
                return None
    except Exception as e:
        logger.warning(f"[AI] Claude: {e}")
        return None


async def _call_gemini(prompt: str, timeout: int = 60) -> Optional[str]:
    """Call Google Gemini API."""
    if not GEMINI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4000},
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            else:
                logger.warning(f"[AI] Gemini: HTTP {resp.status_code}")
                return None
    except Exception as e:
        logger.warning(f"[AI] Gemini: {e}")
        return None


def _parse_model_response(raw: str, model_display: str) -> dict:
    """Parse JSON response from a model, handling common issues."""
    if not raw:
        return {"grade": "?", "score": 0, "confidence": 0, "model": model_display,
                "thesis": "Model unavailable", "key_factors": []}
    try:
        # Try direct parse
        data = json.loads(raw)
        # Could be single game or batch
        if "games" in data:
            return data  # batch response
        # Single game
        data["model"] = model_display
        if "thesis" not in data:
            data["thesis"] = "No reasoning provided"
        return data
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        if "```json" in raw:
            try:
                json_str = raw.split("```json")[1].split("```")[0].strip()
                data = json.loads(json_str)
                data["model"] = model_display
                return data
            except (json.JSONDecodeError, IndexError):
                pass
        # Try to find JSON object in the text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start:end])
                data["model"] = model_display
                return data
            except json.JSONDecodeError:
                pass
    return {"grade": "?", "score": 0, "confidence": 0, "model": model_display,
            "thesis": f"Parse error: {raw[:100]}", "key_factors": []}


# ─── Public API ────────────────────────────────────────────────────────────────

async def crowdsource_grade(games: list, sport: str) -> Dict[str, list]:
    """
    Call multiple AI models to grade games. Returns per-game model grades.
    Result: {game_id: [{"model": "Grok 4.1", "grade": "A-", "score": 7.2, "thesis": "..."}]}
    """
    if not games:
        return {}

    results: Dict[str, list] = {g.get("id", ""): [] for g in games}

    # Build the full model list — add Gemini if key is available
    all_models = list(AI_MODELS)
    if GEMINI_API_KEY:
        all_models.append({
            "name": "gemini-2.5-flash",
            "display": "Gemini 2.5 Flash",
            "endpoint": "gemini",
            "timeout": 60,
            "personality": "probabilistic thinker, injury-aware, sharp on totals and live-line movement",
        })

    for model_cfg in all_models:
        model_name = model_cfg["name"]
        display = model_cfg["display"]
        timeout = model_cfg["timeout"]
        personality = model_cfg["personality"]

        # Build batch prompt
        prompt = _build_batch_prompt(games, personality, sport)

        # Call model — route to correct endpoint
        endpoint_type = model_cfg.get("endpoint", "ai_services")
        logger.info(f"[CROWDSOURCE] Calling {display} ({model_name}) via {endpoint_type} for {len(games)} games")

        if endpoint_type == "gemini":
            raw = await _call_gemini(prompt, timeout)
        else:
            raw = await _call_azure_model(model_name, prompt, timeout, endpoint_type=endpoint_type)

        parsed = _parse_model_response(raw, display)

        if isinstance(parsed, dict) and "games" in parsed:
            # Batch response — match by game_index
            for game_result in parsed["games"]:
                idx = game_result.get("game_index", 0) - 1
                if 0 <= idx < len(games):
                    game_id = games[idx].get("id", "")
                    game_result["model"] = display
                    if game_id in results:
                        results[game_id].append(game_result)
        elif isinstance(parsed, dict) and len(games) == 1:
            # Single game response
            game_id = games[0].get("id", "")
            if game_id in results:
                results[game_id].append(parsed)

    return results


async def kimi_gatekeeper(game: dict, our_grade: dict, ai_grades: list, convergence: dict) -> dict:
    """
    Run Kimi as a post-convergence gatekeeper.
    Reviews the full pipeline output and returns CONFIRM/CHALLENGE/BOOST with reasoning.
    """
    # Kimi K2 Thinking lives at gce-personal-resource (aoai_classic format),
    # matching how app/main.py _call_azure_model routes it in REAL_AI_MODELS.
    key = GCE_KEY or AI_SERVICES_KEY
    if not key:
        return {"action": "?", "adjustment": 0, "reason": "Kimi unavailable — no AZURE_GCE_KEY"}

    home = game.get("homeTeam", "?")
    away = game.get("awayTeam", "?")
    odds = game.get("odds", {})

    # Build model grades summary
    model_lines = []
    for mg in ai_grades:
        model_lines.append(f"  {mg.get('model', '?')}: {mg.get('grade', '?')} ({mg.get('score', 0)}) — {mg.get('thesis', 'no thesis')}")
    models_text = "\n".join(model_lines) if model_lines else "  No AI model grades available"

    prompt = f"""You are EC⁸ Kimi Gatekeeper — the FINAL validation layer.

GAME: {away} @ {home}
ODDS: Spread {odds.get('spread', 0):+.1f} | O/U {odds.get('total', 0)}

OUR PROCESS (Grade Engine):
  Grade: {our_grade.get('grade', '?')} ({our_grade.get('score', 0)})
  Chains: {', '.join(our_grade.get('keyFactors', our_grade.get('chains_fired', [])))}
  Sizing: {our_grade.get('sizing', our_grade.get('thesis', '?'))}

AI PROCESS (Model Grades):
{models_text}

CONVERGENCE: {convergence.get('status', '?')} — Consensus {convergence.get('consensusScore', 0)} ({convergence.get('consensusGrade', '?')})

Your action — be AGGRESSIVE, not a rubber stamp:
- CONFIRM (adj=0): Grade looks right
- CHALLENGE (adj=-1 to -2): Grade too high, something's off
- BOOST (adj=+1 to +2): Grade too low, edge is real

Return ONLY valid JSON:
{{"action": "CONFIRM|CHALLENGE|BOOST", "adjustment": 0, "reason": "1-2 sentences taking a clear side — WHY", "verdict_tag": "SHORT_TAG"}}"""

    # aoai_classic URL — same shape app/main.py uses for gce-hosted deployments.
    url = (
        "https://gce-personal-resource.openai.azure.com/openai/deployments/"
        "Kimi-K2-Thinking/chat/completions?api-version=2024-12-01-preview"
    )
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers={"api-key": key, "Content-Type": "application/json"},
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 6000,
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code != 200:
                err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(f"[GATEKEEPER] {err}")
                return {"action": "?", "adjustment": 0, "reason": err}
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            finish = data.get("choices", [{}])[0].get("finish_reason", "")
            # Strip <think> reasoning block if present
            if "</think>" in content.lower():
                content = content[content.lower().rfind("</think>") + len("</think>"):].strip()
            if not content:
                return {"action": "?", "adjustment": 0,
                        "reason": f"Empty content (finish_reason={finish})"}
            try:
                # Find JSON object in content
                s = content.find("{")
                e = content.rfind("}") + 1
                result = json.loads(content[s:e] if s >= 0 and e > s else content)
            except Exception as pe:
                return {"action": "?", "adjustment": 0,
                        "reason": f"Parse error: {pe} | raw={content[:120]}"}
            logger.info(f"[GATEKEEPER] {away}@{home}: {result.get('action')} adj={result.get('adjustment')} — {str(result.get('reason',''))[:80]}")
            return result
    except httpx.TimeoutException:
        return {"action": "?", "adjustment": 0, "reason": "Gatekeeper timeout (>120s)"}
    except Exception as e:
        logger.warning(f"[GATEKEEPER] Failed: {e}")
        return {"action": "?", "adjustment": 0, "reason": f"Gatekeeper error: {e}"}
