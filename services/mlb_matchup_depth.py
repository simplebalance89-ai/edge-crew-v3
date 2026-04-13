"""MLB Matchup Depth Module — EC8 Round Table expansion.

Adds 5 new matchup scoring functions on top of the existing grade_engine
MLB variables (lineup_vs_hand, pitcher_hitter_archetype, bullpen, etc.).

Each function returns (score, note) on a 1-10 scale, matching the existing
grade_engine pattern. Returns (None, "data unavailable") when upstream data
is missing — callers must handle None gracefully.
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")

MATCHUP_WEIGHTS = {
    "bullpen_sequencing": 1.15,
    "manager_tendencies": 0.85,
    "platoon_depth": 1.00,
    "pitcher_fatigue": 1.20,
    "run_environment": 1.10,
}


def _clamp(val, lo=1, hi=10) -> float:
    return max(lo, min(hi, round(float(val), 1)))


# ─── Scoring Functions ────────────────────────────────────────────────────────


def score_bullpen_sequencing(home_data: dict, away_data: dict) -> dict:
    """Analyze bullpen usage patterns for both sides.

    Reads bullpen sub-dict from each team's profile. Looks at:
    - Relief games in last 7 days (volume)
    - Tired arms (3+ appearances in 7 days)
    - Bullpen IP load (high = overworked pen)
    - ERA trend vs season baseline

    Overworked bullpens score lower. Returns dict with home/away scores.
    """
    results = {}
    for label, data in [("home", home_data), ("away", away_data)]:
        bp = data.get("bullpen") or {}
        if not bp or "bullpen_era_L7" not in bp:
            results[label] = (None, "data unavailable")
            continue

        era_l7 = bp.get("bullpen_era_L7", 4.00)
        tired = bp.get("bullpen_tired_arms", 0)
        relief_games = bp.get("bullpen_relief_games", 0)
        ip_l7 = bp.get("bullpen_ip_L7", 0)
        season_era = bp.get("team_era_season")

        score = 5.0

        if relief_games >= 6:
            score -= 1.0
        elif relief_games >= 4:
            score -= 0.5

        if ip_l7 > 25:
            score -= 1.0
        elif ip_l7 > 18:
            score -= 0.5

        if tired >= 3:
            score -= 1.5
        elif tired >= 2:
            score -= 0.75
        elif tired == 0:
            score += 0.5

        score += (4.00 - era_l7) * 1.0

        if season_era and era_l7 > season_era + 1.0:
            score -= 0.5
        elif season_era and era_l7 < season_era - 1.0:
            score += 0.5

        note_parts = [f"ERA L7 {era_l7:.2f}"]
        if tired:
            note_parts.append(f"{tired} tired arm{'s' if tired != 1 else ''}")
        note_parts.append(f"{relief_games} relief G, {ip_l7:.1f} IP")
        results[label] = (_clamp(score), ", ".join(note_parts))

    return results


def score_manager_tendencies(home_data: dict, away_data: dict) -> dict:
    """Score manager quick-hook vs long-leash tendencies.

    Reads starting_pitcher IP and bullpen usage to infer pull patterns.
    Aggressive managers (short SP leash, high bullpen usage) get a boost
    when their bullpen is fresh, penalty when it's tired.
    """
    results = {}
    for label, data in [("home", home_data), ("away", away_data)]:
        sp = data.get("starting_pitcher") or {}
        bp = data.get("bullpen") or {}

        ip_raw = sp.get("ip")
        relief_games = bp.get("bullpen_relief_games")
        ip_l7 = bp.get("bullpen_ip_L7")
        tired = bp.get("bullpen_tired_arms", 0)

        if ip_raw is None and relief_games is None:
            results[label] = (None, "data unavailable")
            continue

        score = 5.0
        tendencies = []

        if relief_games is not None and ip_l7 is not None:
            avg_relief_ip_per_game = ip_l7 / max(relief_games, 1)
            if avg_relief_ip_per_game > 4.0:
                tendencies.append("quick hook")
                if tired <= 1:
                    score += 1.0
                else:
                    score -= 0.5
            elif avg_relief_ip_per_game < 2.5:
                tendencies.append("long leash")
                score += 0.3

        if ip_raw is not None:
            try:
                season_ip = float(ip_raw)
                games_started_est = max(1, season_ip / 5.5)
                avg_ip_per_start = season_ip / games_started_est
                if avg_ip_per_start < 5.0:
                    tendencies.append("SP pulled early")
                    if tired >= 2:
                        score -= 0.75
                elif avg_ip_per_start > 6.2:
                    tendencies.append("SP goes deep")
                    score += 0.5
            except (ValueError, TypeError):
                pass

        note = ", ".join(tendencies) if tendencies else "neutral tendencies"
        results[label] = (_clamp(score), note)

    return results


def score_platoon_depth(home_data: dict, away_data: dict) -> dict:
    """Score platoon depth beyond just lineup-vs-hand.

    Looks at lineup composition: how many batters in the lineup bat from
    the opposite side of the opposing SP? Deep platoon advantage = more
    bats exploiting the matchup through the order, not just 2-3 hitters.
    Also considers switch hitters as platoon-neutral.
    """
    results = {}
    for label, data, opp_data in [
        ("home", home_data, away_data),
        ("away", away_data, home_data),
    ]:
        lineup = data.get("lineup") or []
        opp_sp = opp_data.get("starting_pitcher") or {}
        opp_hand = opp_sp.get("hand", "")
        splits = data.get("lineup_vs_hand") or {}

        if not lineup or not opp_hand:
            ops = splits.get("ops_vs_hand")
            if ops is not None:
                score = 5.0 + (ops - 0.720) * 30
                results[label] = (_clamp(score), f"OPS vs hand {ops:.3f}, no lineup detail")
                continue
            results[label] = (None, "data unavailable")
            continue

        advantage_side = "L" if opp_hand == "R" else "R"
        adv_count = 0
        switch_count = 0
        for batter in lineup:
            bats = (batter.get("bats") or "").upper()
            if bats == "S":
                switch_count += 1
                adv_count += 1
            elif bats == advantage_side:
                adv_count += 1

        score = 5.0
        if adv_count >= 7:
            score += 2.0
        elif adv_count >= 5:
            score += 1.0
        elif adv_count >= 3:
            score += 0.3
        elif adv_count <= 1:
            score -= 1.5

        ops = splits.get("ops_vs_hand")
        if ops is not None:
            score += (ops - 0.720) * 20

        note = f"{adv_count}/9 bat {advantage_side} vs {opp_hand}HP"
        if switch_count:
            note += f" ({switch_count} switch)"
        if ops is not None:
            note += f", OPS {ops:.3f}"
        results[label] = (_clamp(score), note)

    return results


def score_pitcher_fatigue(home_data: dict, away_data: dict) -> dict:
    """Score pitcher fatigue risk.

    Looks at: season IP load (high = fatigue risk late season), K/9 and
    BB/9 trends (command erodes with fatigue), ERA as a performance signal.
    Pitchers with high workloads and rising ERAs = red flag.
    """
    results = {}
    for label, data in [("home", home_data), ("away", away_data)]:
        sp = data.get("starting_pitcher") or {}
        if not sp or not sp.get("name"):
            results[label] = (None, "data unavailable")
            continue

        ip_raw = sp.get("ip")
        era = sp.get("era")
        k9 = sp.get("k9")
        bb9 = sp.get("bb9")

        if ip_raw is None and era is None:
            results[label] = (None, "data unavailable")
            continue

        score = 5.0
        note_parts = [sp.get("name", "?")]

        if ip_raw is not None:
            try:
                ip = float(ip_raw)
                if ip > 180:
                    score -= 1.5
                    note_parts.append(f"{ip:.0f} IP (heavy load)")
                elif ip > 150:
                    score -= 0.75
                    note_parts.append(f"{ip:.0f} IP (moderate load)")
                elif ip > 100:
                    note_parts.append(f"{ip:.0f} IP")
                elif ip < 40:
                    score += 0.5
                    note_parts.append(f"{ip:.0f} IP (fresh)")
            except (ValueError, TypeError):
                pass

        if era is not None:
            try:
                era_f = float(era)
                if era_f > 4.50:
                    score -= 1.0
                elif era_f > 3.80:
                    score -= 0.3
                elif era_f < 2.80:
                    score += 1.0
                elif era_f < 3.30:
                    score += 0.5
                note_parts.append(f"ERA {era_f:.2f}")
            except (ValueError, TypeError):
                pass

        if bb9 is not None:
            try:
                bb9_f = float(bb9)
                if bb9_f >= 4.0:
                    score -= 0.75
                    note_parts.append(f"BB/9 {bb9_f:.1f} (control issues)")
                elif bb9_f >= 3.5:
                    score -= 0.3
                elif bb9_f <= 2.0:
                    score += 0.5
            except (ValueError, TypeError):
                pass

        if k9 is not None and ip_raw is not None:
            try:
                k9_f = float(k9)
                ip_f = float(ip_raw)
                if ip_f > 150 and k9_f < 7.0:
                    score -= 0.5
                    note_parts.append("K rate declining w/ workload")
            except (ValueError, TypeError):
                pass

        results[label] = (_clamp(score), ", ".join(note_parts))

    return results


def score_run_environment(
    home_data: dict, away_data: dict, park_factor: int | float | None
) -> dict:
    """Combine park factor, weather, and team power numbers for a run
    environment score.

    park_factor: FanGraphs-style (100 = neutral, >100 = hitter-friendly).
    Weather comes from home_data or away_data weather sub-dict.
    Power signal comes from runs_l10 and lineup_vs_hand OPS.
    """
    weather = home_data.get("weather") or away_data.get("weather") or {}

    results = {}
    for label, data in [("home", home_data), ("away", away_data)]:
        score = 5.0
        note_parts = []

        if park_factor is not None:
            try:
                pf = float(park_factor)
                pf_adj = (pf - 100) * 0.15
                score += pf_adj
                note_parts.append(f"PF {int(pf)}")
            except (ValueError, TypeError):
                pass

        temp = weather.get("temp")
        if temp is not None:
            try:
                t = int(temp)
                if t >= 85:
                    score += 0.5
                    note_parts.append(f"{t}°F (hot)")
                elif t >= 75:
                    score += 0.2
                elif t <= 50:
                    score -= 0.5
                    note_parts.append(f"{t}°F (cold)")
                elif t <= 60:
                    score -= 0.2
            except (ValueError, TypeError):
                pass

        wind = weather.get("wind") or ""
        if wind:
            wind_lower = wind.lower()
            if "out" in wind_lower and ("mph" in wind_lower):
                try:
                    mph = int("".join(c for c in wind_lower.split("mph")[0].strip().split()[-1] if c.isdigit()))
                    if mph >= 15:
                        score += 1.0
                        note_parts.append(f"wind out {mph}mph")
                    elif mph >= 10:
                        score += 0.5
                except (ValueError, IndexError):
                    pass
            elif "in" in wind_lower and ("mph" in wind_lower):
                try:
                    mph = int("".join(c for c in wind_lower.split("mph")[0].strip().split()[-1] if c.isdigit()))
                    if mph >= 15:
                        score -= 1.0
                        note_parts.append(f"wind in {mph}mph")
                    elif mph >= 10:
                        score -= 0.5
                except (ValueError, IndexError):
                    pass

        runs_l10 = data.get("runs_l10") or {}
        rpg = runs_l10.get("runs_for_l10")
        if rpg is not None:
            try:
                rpg_f = float(rpg)
                if rpg_f >= 5.5:
                    score += 0.75
                    note_parts.append(f"{rpg_f:.1f} R/G L10")
                elif rpg_f >= 4.5:
                    score += 0.3
                elif rpg_f < 3.5:
                    score -= 0.75
                    note_parts.append(f"{rpg_f:.1f} R/G L10")
            except (ValueError, TypeError):
                pass

        ops = (data.get("lineup_vs_hand") or {}).get("ops_vs_hand")
        if ops is not None:
            try:
                ops_f = float(ops)
                if ops_f >= 0.780:
                    score += 0.5
                elif ops_f <= 0.680:
                    score -= 0.5
            except (ValueError, TypeError):
                pass

        if not note_parts:
            note_parts.append("baseline only")
        results[label] = (_clamp(score), ", ".join(note_parts))

    return results


# ─── Aggregator ───────────────────────────────────────────────────────────────


def get_all_matchup_scores(
    home_data: dict, away_data: dict, park_factor: int | float | None = None
) -> dict:
    """Run all 5 matchup depth functions and return a unified result dict.

    Returns:
        {
            "bullpen_sequencing": {"home": (score, note), "away": (score, note)},
            "manager_tendencies": {"home": ..., "away": ...},
            "platoon_depth":      {"home": ..., "away": ...},
            "pitcher_fatigue":    {"home": ..., "away": ...},
            "run_environment":    {"home": ..., "away": ...},
        }
    """
    return {
        "bullpen_sequencing": score_bullpen_sequencing(home_data, away_data),
        "manager_tendencies": score_manager_tendencies(home_data, away_data),
        "platoon_depth": score_platoon_depth(home_data, away_data),
        "pitcher_fatigue": score_pitcher_fatigue(home_data, away_data),
        "run_environment": score_run_environment(home_data, away_data, park_factor),
    }
