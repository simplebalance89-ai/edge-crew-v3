"""
Edge Crew v3 — Forecaster Scoring & Calibration
Tracks model accuracy over time, computes dynamic weights for the crowdsource layer.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("edge-crew-v3")

SCORES_FILE = os.path.join(os.path.dirname(__file__), "data", "forecaster_scores.json")

GRADE_MAP = {
    "A+": 9.5, "A": 8.5, "A-": 7.5, "B+": 7.0, "B": 6.5, "B-": 6.0,
    "C+": 5.5, "C": 5.0, "D": 3.5, "F": 2.0,
}

WEIGHT_FLOOR = 0.05
ROLLING_WINDOW = 30

# Weight formula: overall accuracy 40%, recent form 35%, sport-specific 25%
W_OVERALL = 0.40
W_RECENT = 0.35
W_SPORT = 0.25

ALL_MODEL_NAMES = [
    "Azure Model Router",
    "Grok 4.20 Reasoning",
    "Grok 4.1",
    "Grok 4 Fast",
    "Grok 3",
    "DeepSeek R1",
    "DeepSeek V3.2 Spec",
    "DeepSeek V3.1",
    "Phi-4 Reasoning",
    "GPT-4.1",
    "GPT-5 Mini",
    "GPT-5.2 Chat",
    "GPT-5.4 Nano",
    "Llama-4 Maverick",
    "Llama-4 Scout",
    "Mistral Large 3",
    "Kimi K2.5 (Azure)",
    "Claude Sonnet 4.6",
    "Qwen 3.6 Plus",
    "Gemini 2.5 Flash",
    "Perplexity Sonar",
]


# ─── Storage ─────────────────────────────────────────────────────────────────

def _load_data() -> dict:
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("[SCORING] Corrupt scores file, starting fresh")
    return {"predictions": {}, "outcomes": {}, "version": 1}


def _save_data(data: dict):
    os.makedirs(os.path.dirname(SCORES_FILE), exist_ok=True)
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Integration Hooks ───────────────────────────────────────────────────────

def record_prediction(game_id: str, model_name: str, grade: str, pick: str, sport: str, score: float = 0.0):
    """Record a model's prediction for a game. Called after crowdsource_grade."""
    data = _load_data()
    preds = data.setdefault("predictions", {})
    game_preds = preds.setdefault(game_id, {})
    game_preds[model_name] = {
        "grade": grade,
        "score": score or GRADE_MAP.get(grade, 5.0),
        "pick": pick,
        "sport": sport.upper(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _save_data(data)


def record_outcome(game_id: str, actual_winner: str, actual_margin: float):
    """Record the actual game result. Called when games settle."""
    data = _load_data()
    outcomes = data.setdefault("outcomes", {})
    outcomes[game_id] = {
        "winner": actual_winner,
        "margin": actual_margin,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _save_data(data)


# ─── Accuracy Metrics ────────────────────────────────────────────────────────

def _grade_distance(predicted_score: float, actual_margin: float) -> float:
    """How close was the model's confidence to the actual margin of victory.
    Lower is better. Normalized to 0-1 scale (1 = perfect, 0 = way off)."""
    norm_pred = predicted_score / 10.0
    norm_margin = min(abs(actual_margin) / 30.0, 1.0)
    return max(0.0, 1.0 - abs(norm_pred - norm_margin))


def get_model_metrics() -> Dict[str, dict]:
    """Compute accuracy metrics for every model that has graded predictions."""
    data = _load_data()
    preds = data.get("predictions", {})
    outcomes = data.get("outcomes", {})

    settled_games = set(preds.keys()) & set(outcomes.keys())
    if not settled_games:
        return {}

    model_records: Dict[str, list] = defaultdict(list)

    for game_id in settled_games:
        outcome = outcomes[game_id]
        winner = outcome["winner"].strip().lower()
        margin = outcome["margin"]

        for model_name, pred in preds[game_id].items():
            pick_correct = pred["pick"].strip().lower() == winner
            grade_acc = _grade_distance(pred["score"], margin)
            model_records[model_name].append({
                "game_id": game_id,
                "sport": pred.get("sport", "UNKNOWN"),
                "grade": pred["grade"],
                "score": pred["score"],
                "pick_correct": pick_correct,
                "grade_accuracy": grade_acc,
                "ts": pred.get("ts", ""),
            })

    metrics = {}
    for model_name, records in model_records.items():
        records.sort(key=lambda r: r["ts"], reverse=True)
        total = len(records)
        wins = sum(1 for r in records if r["pick_correct"])
        avg_grade_acc = sum(r["grade_accuracy"] for r in records) / total

        recent = records[:ROLLING_WINDOW]
        recent_wins = sum(1 for r in recent if r["pick_correct"])
        recent_total = len(recent)

        sport_breakdown = defaultdict(lambda: {"total": 0, "wins": 0, "grade_acc_sum": 0.0})
        for r in records:
            s = sport_breakdown[r["sport"]]
            s["total"] += 1
            if r["pick_correct"]:
                s["wins"] += 1
            s["grade_acc_sum"] += r["grade_accuracy"]

        sport_stats = {}
        for sport, s in sport_breakdown.items():
            sport_stats[sport] = {
                "total": s["total"],
                "win_rate": s["wins"] / s["total"],
                "grade_accuracy": s["grade_acc_sum"] / s["total"],
            }

        calibration = _compute_calibration(records)

        metrics[model_name] = {
            "total_picks": total,
            "win_rate": wins / total,
            "grade_accuracy": avg_grade_acc,
            "calibration": calibration,
            "l30_win_rate": recent_wins / recent_total if recent_total > 0 else 0.0,
            "l30_total": recent_total,
            "per_sport": sport_stats,
        }

    return metrics


def _compute_calibration(records: list) -> float:
    """Are A+ picks winning more than B picks? Returns 0-1 (1 = perfectly calibrated)."""
    tier_buckets = {"high": [], "mid": [], "low": []}
    for r in records:
        score = r["score"]
        if score >= 7.5:
            tier_buckets["high"].append(r["pick_correct"])
        elif score >= 5.5:
            tier_buckets["mid"].append(r["pick_correct"])
        else:
            tier_buckets["low"].append(r["pick_correct"])

    rates = {}
    for tier, outcomes in tier_buckets.items():
        if outcomes:
            rates[tier] = sum(outcomes) / len(outcomes)

    if len(rates) < 2:
        return 0.5

    high_r = rates.get("high", 0.5)
    mid_r = rates.get("mid", 0.5)
    low_r = rates.get("low", 0.5)

    if high_r >= mid_r >= low_r:
        return 1.0
    if high_r >= mid_r or high_r >= low_r:
        return 0.7
    return 0.3


# ─── Dynamic Weight Calculator ───────────────────────────────────────────────

def get_model_weights(sport: Optional[str] = None) -> Dict[str, float]:
    """Return model_name -> weight (0.0-1.0) based on historical accuracy.
    If no data exists yet, returns equal weights for all known models."""
    all_model_names = ALL_MODEL_NAMES

    metrics = get_model_metrics()
    if not metrics:
        equal = 1.0 / len(all_model_names)
        return {name: equal for name in all_model_names}

    raw_scores = {}
    for model_name in all_model_names:
        m = metrics.get(model_name)
        if not m or m["total_picks"] < 5:
            raw_scores[model_name] = 0.5
            continue

        overall = m["win_rate"] * 0.6 + m["grade_accuracy"] * 0.4
        recent = m["l30_win_rate"] if m["l30_total"] >= 5 else overall

        if sport and sport.upper() in m["per_sport"]:
            sp = m["per_sport"][sport.upper()]
            sport_acc = sp["win_rate"] * 0.6 + sp["grade_accuracy"] * 0.4 if sp["total"] >= 3 else overall
        else:
            sport_acc = overall

        raw_scores[model_name] = (
            W_OVERALL * overall +
            W_RECENT * recent +
            W_SPORT * sport_acc
        )

    raw_scores = {k: max(v, WEIGHT_FLOOR) for k, v in raw_scores.items()}

    total = sum(raw_scores.values())
    if total == 0:
        equal = 1.0 / len(all_model_names)
        return {name: equal for name in all_model_names}

    return {k: round(v / total, 4) for k, v in raw_scores.items()}


def get_scoring_summary() -> dict:
    """Return a quick summary for dashboards/logging."""
    metrics = get_model_metrics()
    weights = get_model_weights()
    return {
        "models_tracked": len(metrics),
        "weights": weights,
        "top_model": max(weights, key=weights.get) if weights else None,
        "metrics": {
            name: {
                "total": m["total_picks"],
                "win_rate": round(m["win_rate"], 3),
                "l30_win_rate": round(m["l30_win_rate"], 3),
                "calibration": round(m["calibration"], 2),
            }
            for name, m in metrics.items()
        },
    }
