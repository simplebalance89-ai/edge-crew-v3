"""
Edge Crew v3 — Dynamic Weight Learning
Tracks game outcomes and adjusts variable weights over time using EMA.
Falls back to hardcoded SPORT_VARIABLES when insufficient data.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import os
import math
from datetime import datetime, timezone
from grade_engine import SPORT_VARIABLES

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
WEIGHT_FILE = os.path.join(DATA_DIR, "weight_learning.json")

LEARNING_RATE = 0.1
MIN_GAMES = 50
WEIGHT_FLOOR = 2
WEIGHT_CEILING = 15


def _load_data() -> dict:
    if os.path.exists(WEIGHT_FILE):
        with open(WEIGHT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"games": [], "adjusted_weights": {}, "last_recalc": {}}


def _save_data(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(WEIGHT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_game_result(game_id: str, sport: str, variable_scores: dict,
                       predicted_grade: str, actual_outcome: str,
                       actual_margin: float = 0.0):
    """
    Record a completed game for weight learning.
    actual_outcome: "W" or "L" (did our pick win?)
    variable_scores: {var_name: score} as computed by the grade engine
    """
    sport = sport.upper()
    data = _load_data()

    record = {
        "game_id": game_id,
        "sport": sport,
        "variable_scores": variable_scores,
        "predicted_grade": predicted_grade,
        "actual_outcome": actual_outcome,
        "actual_margin": actual_margin,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    data["games"].append(record)
    _save_data(data)

    sport_games = [g for g in data["games"] if g["sport"] == sport]
    if len(sport_games) >= MIN_GAMES:
        _recalculate_weights(data, sport)


def _recalculate_weights(data: dict, sport: str):
    """
    EMA-based weight adjustment. For each variable, measure correlation
    between its score and correct outcomes, then nudge weights accordingly.
    """
    sport_games = [g for g in data["games"] if g["sport"] == sport]
    if len(sport_games) < MIN_GAMES:
        return

    defaults = SPORT_VARIABLES.get(sport, SPORT_VARIABLES["NBA"])
    current = data["adjusted_weights"].get(sport, dict(defaults))

    all_vars = set()
    for g in sport_games:
        all_vars.update(g["variable_scores"].keys())

    for var in all_vars:
        if var not in defaults:
            continue

        scores = []
        outcomes = []
        for g in sport_games:
            if var in g["variable_scores"]:
                scores.append(g["variable_scores"][var])
                outcomes.append(1.0 if g["actual_outcome"] == "W" else 0.0)

        if len(scores) < 20:
            continue

        n = len(scores)
        mean_s = sum(scores) / n
        mean_o = sum(outcomes) / n

        cov = sum((scores[i] - mean_s) * (outcomes[i] - mean_o) for i in range(n)) / n
        std_s = math.sqrt(sum((s - mean_s) ** 2 for s in scores) / n) if n > 1 else 0
        std_o = math.sqrt(sum((o - mean_o) ** 2 for o in outcomes) / n) if n > 1 else 0

        if std_s < 0.001 or std_o < 0.001:
            continue

        correlation = cov / (std_s * std_o)

        base_weight = defaults[var]
        adjustment = correlation * LEARNING_RATE * base_weight
        new_weight = current.get(var, base_weight) + adjustment
        new_weight = max(WEIGHT_FLOOR, min(WEIGHT_CEILING, round(new_weight, 2)))
        current[var] = new_weight

    data["adjusted_weights"][sport] = current
    data["last_recalc"][sport] = datetime.now(timezone.utc).isoformat()
    _save_data(data)


def get_adjusted_weights(sport: str) -> dict:
    """
    Returns adjusted weights for a sport if enough data exists,
    otherwise returns the hardcoded defaults from SPORT_VARIABLES.
    """
    sport = sport.upper()
    defaults = SPORT_VARIABLES.get(sport, SPORT_VARIABLES["NBA"])

    data = _load_data()
    sport_games = [g for g in data["games"] if g["sport"] == sport]

    if len(sport_games) < MIN_GAMES:
        return dict(defaults)

    adjusted = data.get("adjusted_weights", {}).get(sport)
    if not adjusted:
        return dict(defaults)

    merged = dict(defaults)
    merged.update(adjusted)
    return merged


def get_weight_report(sport: str) -> str:
    """
    Readable summary of weight shifts from defaults.
    """
    sport = sport.upper()
    defaults = SPORT_VARIABLES.get(sport, SPORT_VARIABLES["NBA"])
    data = _load_data()

    sport_games = [g for g in data["games"] if g["sport"] == sport]
    game_count = len(sport_games)
    wins = sum(1 for g in sport_games if g["actual_outcome"] == "W")

    lines = [f"=== Weight Report: {sport} ==="]
    lines.append(f"Games tracked: {game_count}")
    if game_count > 0:
        lines.append(f"Win rate: {wins}/{game_count} ({100*wins/game_count:.1f}%)")
    lines.append("")

    if game_count < MIN_GAMES:
        lines.append(f"Need {MIN_GAMES - game_count} more games before weights adjust.")
        lines.append("Currently using hardcoded defaults.")
        return "\n".join(lines)

    adjusted = data.get("adjusted_weights", {}).get(sport, {})
    last_recalc = data.get("last_recalc", {}).get(sport, "never")
    lines.append(f"Last recalculation: {last_recalc}")
    lines.append("")

    shifts = []
    for var, default_w in sorted(defaults.items(), key=lambda x: x[1], reverse=True):
        current_w = adjusted.get(var, default_w)
        delta = current_w - default_w
        if abs(delta) >= 0.05:
            direction = "+" if delta > 0 else ""
            shifts.append((var, default_w, current_w, delta, direction))

    if shifts:
        lines.append("Variable adjustments (from default):")
        for var, default_w, current_w, delta, direction in shifts:
            lines.append(f"  {var:25s}  {default_w:>5} -> {current_w:>6}  ({direction}{delta:.2f})")
    else:
        lines.append("No significant weight shifts yet.")

    unchanged = [var for var in defaults if abs(adjusted.get(var, defaults[var]) - defaults[var]) < 0.05]
    if unchanged:
        lines.append(f"\nUnchanged ({len(unchanged)}): {', '.join(sorted(unchanged))}")

    return "\n".join(lines)
