"""
Edge Crew v3 — Compact Grade Engine
Ported from v2's 3K-line engine into a clean, self-contained module.
Pure math grading: variables → composite → chains → final grade.
"""

import math

# ─── Grade Thresholds ──────────────────────────────────────────────────────────

GRADE_THRESHOLDS = [
    (8.0, "A+"), (7.3, "A"), (6.5, "A-"),
    (6.0, "B+"), (5.5, "B"), (5.0, "B-"),
    (4.5, "C+"), (3.5, "C"), (2.5, "D"), (0.0, "F"),
]

SIZING_MAP = {
    "A+": "2u", "A": "1.5u", "A-": "1u", "B+": "1u",
    "B": "PASS", "B-": "PASS", "C+": "PASS", "C": "PASS",
    "D": "PASS", "F": "PASS",
}


def score_to_grade(score: float) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def score_to_sizing(score: float) -> str:
    return SIZING_MAP.get(score_to_grade(score), "PASS")


def _clamp(val, lo=1, hi=10) -> float:
    return max(lo, min(hi, round(float(val), 1)))


def _parse_record(rec: str | None) -> tuple:
    if not rec:
        return 0, 0
    try:
        parts = rec.split("-")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


def _win_pct(rec: str | None) -> float:
    w, l = _parse_record(rec)
    return w / (w + l) if (w + l) > 0 else 0.5


# ─── Variable Scoring Functions ────────────────────────────────────────────────
# Each returns (score: 1-10, note: str)

def score_off_ranking(profile: dict, opp: dict, sport: str) -> tuple:
    ppg = profile.get("ppg_L5", 0)
    opp_def = opp.get("opp_ppg_L5", 0)
    if not ppg:
        return 5, "No PPG data"
    breakpoints = {
        "NBA":   [(122,9),(118,7.5),(114,6),(110,5),(105,4),(0,2.5)],
        "NHL":   [(4.0,9),(3.5,7),(3.0,5),(2.5,3.5),(0,2)],
        "MLB":   [(6.0,9),(5.5,7.5),(5.0,6),(4.5,5),(4.0,3.5),(0,2)],
        "NFL":   [(27,9),(24,7.5),(21,6),(18,5),(15,3.5),(0,2)],
        "SOCCER":[(2.5,9),(2.0,7.5),(1.5,6),(1.2,5),(0.8,3.5),(0,2)],
        "NCAAB": [(82,9),(78,7.5),(74,6),(70,5),(65,3.5),(0,2)],
    }
    base = 5
    for threshold, val in breakpoints.get(sport, breakpoints["NBA"]):
        if ppg >= threshold:
            base = val
            break
    if opp_def:
        avg_map = {"NBA": (115, 100), "NHL": (3.5, 2.5), "MLB": (5.5, 3.5), "NFL": (24, 17), "SOCCER": (2.0, 1.0)}
        hi, lo = avg_map.get(sport, (115, 100))
        if opp_def >= hi:
            base += 0.5
        elif opp_def <= lo:
            base -= 0.5
    return _clamp(base), f"PPG L5: {ppg} | OPP allows: {opp_def}"


def score_def_ranking(profile: dict, opp: dict, sport: str) -> tuple:
    opp_ppg = profile.get("opp_ppg_L5", 0)
    if not opp_ppg:
        return 5, "No OPP PPG data"
    breakpoints = {
        "NBA":   [(100,9),(105,7.5),(110,6),(114,5),(118,3.5),(999,2)],
        "NHL":   [(2.0,9),(2.5,7),(3.0,5),(3.5,3.5),(999,2)],
        "MLB":   [(3.0,9),(3.5,7.5),(4.0,6),(4.5,5),(5.5,3.5),(999,2)],
        "NFL":   [(15,9),(18,7.5),(21,6),(24,5),(27,3.5),(999,2)],
        "SOCCER":[(0.5,9),(0.8,7.5),(1.0,6),(1.3,5),(1.8,3.5),(999,2)],
        "NCAAB": [(62,9),(66,7.5),(70,5),(75,3.5),(999,2)],
    }
    base = 5
    for threshold, val in breakpoints.get(sport, breakpoints["NBA"]):
        if opp_ppg <= threshold:
            base = val
            break
    return _clamp(base), f"Allow L5: {opp_ppg}"


def score_recent_form(profile: dict, opp: dict) -> tuple:
    w, l = _parse_record(profile.get("L5"))
    ow, _ = _parse_record(opp.get("L5"))
    streak = profile.get("streak", "")
    margin = profile.get("L5_margin", profile.get("margin_L5", 0))
    if w + l == 0:
        return 5, "No L5 data"
    base = {5: 9, 4: 7, 3: 5, 2: 3.5, 1: 2, 0: 1}.get(w, 5)
    if streak.startswith("W"):
        n = int(streak[1:]) if streak[1:].isdigit() else 0
        base += 1.5 if n >= 6 else (0.5 if n >= 3 else 0)
    elif streak.startswith("L"):
        n = int(streak[1:]) if streak[1:].isdigit() else 0
        base -= 1.5 if n >= 6 else (0.5 if n >= 3 else 0)
    form_edge = w - ow
    if form_edge >= 3: base += 1
    elif form_edge <= -3: base -= 1
    if margin > 10: base += 0.5
    elif margin < -10: base -= 0.5
    return _clamp(base), f"L5: {profile.get('L5','?')} streak:{streak} margin:{margin:+.1f}"


def score_home_away(game: dict, side: str) -> tuple:
    profile = game.get(f"{side}_profile", {})
    is_home = side == "home"
    base = 5.5 if is_home else 4.5
    rec_key = "home_record" if is_home else "away_record"
    w, l = _parse_record(profile.get(rec_key))
    if w + l > 0:
        pct = w / (w + l)
        if pct >= 0.7: base += 2
        elif pct >= 0.55: base += 1
        elif pct <= 0.3: base -= 2
        elif pct <= 0.4: base -= 1
    return _clamp(base), f"{'Home' if is_home else 'Away'}: {profile.get(rec_key, '?')}"


def score_rest_advantage(profile: dict, opp: dict) -> tuple:
    our_rest = profile.get("rest_days")
    opp_rest = opp.get("rest_days")
    our_b2b = profile.get("is_b2b", False)
    opp_b2b = opp.get("is_b2b", False)
    if our_rest is None or opp_rest is None:
        return 5, "Rest data unavailable"
    score = 5
    parts = []
    if opp_b2b and not our_b2b:
        score += 3; parts.append("OPP on B2B")
    elif our_b2b and not opp_b2b:
        score -= 3; parts.append("WE on B2B")
    rest_diff = (our_rest or 0) - (opp_rest or 0)
    if rest_diff >= 3: score += 2
    elif rest_diff >= 1: score += 1
    elif rest_diff <= -3: score -= 2
    elif rest_diff <= -1: score -= 1
    return _clamp(score), f"Us:{our_rest}d Them:{opp_rest}d {'; '.join(parts)}"


def score_h2h(profile: dict) -> tuple:
    h2h = profile.get("h2h_season", "0-0")
    w, l = _parse_record(h2h)
    if w + l == 0:
        return 5, "No H2H"
    pct = w / (w + l)
    if pct >= 0.75 and w + l >= 2: score = 9
    elif pct >= 0.6: score = 7
    elif pct == 0.5: score = 5
    elif pct <= 0.25 and w + l >= 2: score = 2
    elif pct <= 0.4: score = 3
    else: score = 5
    return _clamp(score), f"H2H: {h2h}"


def score_star_player(game: dict, side: str) -> tuple:
    opp_side = "away" if side == "home" else "home"
    opp_inj = game.get("injuries", {}).get(opp_side, [])
    our_inj = game.get("injuries", {}).get(side, [])
    opp_impact = our_impact = 0
    for inj in opp_inj:
        if inj.get("status") in ("OUT", "DOUBTFUL"):
            ppg = inj.get("ppg", 0)
            disc = 0.5 if inj.get("freshness") in ("ESTABLISHED", "SEASON") else 1.0
            opp_impact += (3 if ppg >= 20 else 2 if ppg >= 12 else 0.5) * disc
    for inj in our_inj:
        if inj.get("status") in ("OUT", "DOUBTFUL"):
            ppg = inj.get("ppg", 0)
            disc = 0.5 if inj.get("freshness") in ("ESTABLISHED", "SEASON") else 1.0
            our_impact += (3 if ppg >= 20 else 2 if ppg >= 12 else 0.5) * disc

    opp_out_count = sum(1 for inj in opp_inj if inj.get("status") in ("OUT", "DOUBTFUL"))
    if opp_out_count >= 5:
        opp_impact = max(opp_impact, 8.0)
    elif opp_out_count >= 4:
        opp_impact = max(opp_impact, 6.0)
    elif opp_out_count >= 3:
        opp_impact = max(opp_impact, 4.0)

    own_out_count = sum(1 for inj in our_inj if inj.get("status") in ("OUT", "DOUBTFUL"))
    if own_out_count >= 5:
        own_penalty = -4.0
    elif own_out_count >= 4:
        own_penalty = -3.0
    elif own_out_count >= 3:
        own_penalty = -2.0
    else:
        own_penalty = 0

    note = f"Injury diff: +{opp_impact:.1f} -{our_impact:.1f}"
    if opp_out_count >= 3:
        note += f" | OPP rest({opp_out_count} out)"
    if own_out_count >= 3:
        note += f" | OWN rest({own_out_count} out)"
    return _clamp(5 + opp_impact - our_impact + own_penalty), note


def score_depth_injuries(game: dict, side: str) -> tuple:
    opp_side = "away" if side == "home" else "home"
    opp_out = len([i for i in game.get("injuries", {}).get(opp_side, []) if i.get("status") in ("OUT", "DOUBTFUL")])
    our_out = len([i for i in game.get("injuries", {}).get(side, []) if i.get("status") in ("OUT", "DOUBTFUL")])
    diff = opp_out - our_out
    if diff >= 4: score = 9
    elif diff >= 2: score = 7
    elif diff >= 0: score = 5
    elif diff >= -2: score = 4
    else: score = 2
    return _clamp(score), f"Them:{opp_out} out Us:{our_out} out"


def score_line_movement(game: dict) -> tuple:
    shifts = game.get("shifts", {})
    delta = abs(shifts.get("spread_delta", 0))
    if delta >= 3: return 9, f"BIG MOVE: {delta:.1f} pts"
    elif delta >= 1.5: return 7, f"Sig move: {delta:.1f} pts"
    elif delta >= 0.5: return 5, f"Moved {delta:.1f} pts"
    return 5, "Line flat"


def score_ats_trend(profile: dict) -> tuple:
    margin = profile.get("avg_margin_L10", 0)
    if margin >= 10: return 9, f"Margin L10: {margin:+.1f}"
    elif margin >= 5: return 7, f"Margin L10: {margin:+.1f}"
    elif margin >= 0: return 5, f"Margin L10: {margin:+.1f}"
    elif margin >= -5: return 4, f"Margin L10: {margin:+.1f}"
    return 2, f"Margin L10: {margin:+.1f}"


def score_road_trip(profile: dict) -> tuple:
    road = profile.get("road_trip_len", 0)
    home = profile.get("home_stand_len", 0)
    if home >= 4: return 6, f"Home stand: {home}"
    elif home >= 2: return 5.5, f"Home stand: {home}"
    elif road >= 5: return 2, f"Road trip: {road}"
    elif road >= 3: return 4, f"Road trip: {road}"
    return 5, "Neutral"


def score_pp_pct(profile: dict) -> tuple:
    pp = profile.get("pp_pct")
    if pp is None:
        return 5, "no PP data"
    if pp >= 25:
        return 9, f"PP {pp:.1f}%"
    if pp >= 22:
        return 7, f"PP {pp:.1f}%"
    if pp >= 20:
        return 5, f"PP {pp:.1f}%"
    if pp >= 18:
        return 3, f"PP {pp:.1f}%"
    return 2, f"PP {pp:.1f}% (weak)"


def score_pk_pct(profile: dict) -> tuple:
    pk = profile.get("pk_pct")
    if pk is None:
        return 5, "no PK data"
    if pk >= 84:
        return 9, f"PK {pk:.1f}%"
    if pk >= 80:
        return 7, f"PK {pk:.1f}%"
    if pk >= 78:
        return 5, f"PK {pk:.1f}%"
    if pk >= 75:
        return 3, f"PK {pk:.1f}%"
    return 2, f"PK {pk:.1f}% (weak)"


def score_goalie_workload(game: dict, side: str) -> tuple:
    profile = game.get(f"{side}_profile", {}) or {}
    g = profile.get("starting_goalie") or {}
    our_sv = _normalize_sv_pct(g.get("sv_pct") or g.get("SV%") or g.get("svp"))
    if our_sv is None:
        return 5, "No goalie workload data"
    if our_sv >= 0.925:
        return _clamp(3), f"SV% {our_sv:.3f} — fresh/elite"
    elif our_sv >= 0.915:
        return _clamp(4), f"SV% {our_sv:.3f} — manageable"
    elif our_sv >= 0.905:
        return _clamp(6), f"SV% {our_sv:.3f} — moderate load"
    elif our_sv >= 0.900:
        return _clamp(7), f"SV% {our_sv:.3f} — heavy"
    else:
        return _clamp(8), f"SV% {our_sv:.3f} — overworked/struggling"


def score_b2b_flag(profile: dict) -> tuple:
    rest = profile.get("rest_days")
    if rest is None:
        return 5, "No rest data"
    if rest <= 1:
        return _clamp(9), f"B2B — {rest}d rest"
    elif rest == 2:
        return _clamp(5), f"{rest}d rest — normal"
    else:
        return _clamp(2), f"{rest}d rest — well rested"


def score_shot_quality(profile: dict, opp: dict) -> tuple:
    pace = profile.get("nhl_pace") or {}
    opp_pace = opp.get("nhl_pace") or {}
    sf = pace.get("shots_for_per_game")
    sa = opp_pace.get("shots_against_per_game")
    if sf is None or sa is None:
        return 5, "No shot quality data"
    diff = sf - sa
    if diff >= 5:
        score = 8.5
    elif diff >= 3:
        score = 7.0
    elif diff >= 1:
        score = 6.0
    elif diff >= -1:
        score = 5.0
    elif diff >= -3:
        score = 4.0
    else:
        score = 2.5
    return _clamp(score), f"SF/g {sf:.1f} vs OPP SA/g {sa:.1f} (Δ{diff:+.1f})"


def score_travel_fatigue(profile: dict, game: dict, side: str) -> tuple:
    road = profile.get("road_trip_len", 0)
    rest = profile.get("rest_days")
    is_home = (side == "home")
    if rest is None:
        rest = 3
    if is_home and rest >= 2:
        return _clamp(2), f"Home + {rest}d rest — fresh"
    elif is_home:
        return _clamp(4), f"Home + {rest}d rest"
    if road >= 5 and rest <= 1:
        return _clamp(8), f"Road trip {road}g + {rest}d rest — heavy fatigue"
    elif road >= 3 and rest <= 1:
        return _clamp(7), f"Road trip {road}g + {rest}d rest — fatigued"
    elif road >= 3:
        return _clamp(5), f"Road trip {road}g + {rest}d rest"
    return _clamp(4), f"Road {road}g + {rest}d rest — manageable"


def score_pace_matchup(profile: dict, opp: dict, sport: str) -> tuple:
    our = profile.get("pace_L5", 0)
    their = opp.get("pace_L5", 0)
    if not our or not their:
        return 5, "No pace data"
    diff = abs(our - their)
    if sport == "NBA":
        if our >= 235 and their >= 235: return 5.5, "FAST matchup"
        elif our <= 210 and their <= 210: return 5, "Grind game"
        elif diff >= 20: return 3.5, f"PACE MISMATCH: {diff:.0f}"
    if sport == "NHL":
        # pace_L5 = combined shots-for + shots-against per game from
        # services.nhl_pace. League average ~60; high-pace 65+; grind <55.
        avg = (our + their) / 2
        if avg >= 65:
            return 7.0, f"FAST matchup ({avg:.1f} sh/g)"
        elif avg <= 55:
            return 4.0, f"Grind game ({avg:.1f} sh/g)"
        elif diff >= 8:
            return 6.0, f"Pace mismatch: {diff:.1f} sh/g"
        return 5.5, f"Pace diff: {diff:.1f} sh/g"
    if sport in ("NFL", "NCAAF"):
        # pace_L5 = offensive plays per game from services.espn_pace.
        # NFL average ~63 plays/game; high-tempo 68+; slow grind <58.
        avg = (our + their) / 2
        if avg >= 68:
            return 7.0, f"HIGH-TEMPO ({avg:.1f} plays/g)"
        elif avg <= 58:
            return 4.0, f"Slow grind ({avg:.1f} plays/g)"
        elif diff >= 5:
            return 6.0, f"Pace mismatch: {diff:.1f} plays/g"
        return 5.5, f"Pace diff: {diff:.1f} plays/g"
    if sport == "NCAAB":
        # pace_L5 = possessions proxy (FGA + 0.44*FTA) per game.
        # CBB average ~70 possessions; high-pace 75+; grind <65.
        avg = (our + their) / 2
        if avg >= 75:
            return 7.0, f"FAST matchup ({avg:.1f} pos/g)"
        elif avg <= 65:
            return 4.0, f"Grind game ({avg:.1f} pos/g)"
        elif diff >= 7:
            return 6.0, f"Pace mismatch: {diff:.1f} pos/g"
        return 5.5, f"Pace diff: {diff:.1f} pos/g"
    return 5, f"Pace diff: {diff:.0f}"


# ─── NBA-Specific Scorers (quarter splits, late-game closing, bench) ──────────

def score_late_game_strength(game: dict, side: str) -> tuple:
    """NBA Phoenix-blows-leads variable. Reads profile.nba_quarters.

    5.0 neutral, >=7.5 strong closer, <=2.5 collapse-prone.
    Marks unavailable upstream when no quarter data is present.
    """
    profile = game.get(f"{side}_profile", {}) or {}
    q = profile.get("nba_quarters") or {}
    if not q:
        return 5.0, "no quarter data"
    blown = q.get("leads_blown_l10", 0) or 0
    comebacks = q.get("comebacks_l10", 0) or 0
    label = q.get("label", "L10")
    score = 5.0 + (comebacks - blown) * 1.25
    if blown >= 3 and comebacks == 0:
        score = min(score, 2.5)
    if blown == 0 and comebacks >= 2:
        score = max(score, 7.5)
    note = f"closing {label}: blown {blown} / comebacks {comebacks}"
    if score >= 7.5:
        note += " (strong closer)"
    elif score <= 2.5:
        note += " (collapse-prone)"
    return _clamp(score), note


def score_quarter_pace(game: dict, side: str) -> tuple:
    """NBA quarter rhythm vs opponent. Reads q1/q4 averages from
    nba_quarters for both teams. Anchored at 5.0; +/-1 per matched edge.
    """
    opp_side = "away" if side == "home" else "home"
    us = (game.get(f"{side}_profile", {}) or {}).get("nba_quarters") or {}
    them = (game.get(f"{opp_side}_profile", {}) or {}).get("nba_quarters") or {}
    if not us or not them:
        return 5.0, "no quarter data"

    base = 5.0
    parts = []

    our_q1_for = us.get("q1_avg_for", 0) or 0
    opp_q1_def = them.get("q1_avg_against", 0) or 0
    if our_q1_for >= 28 and opp_q1_def >= 28:
        base += 1
        parts.append("Q1 attack vs weak Q1 D")
    elif our_q1_for <= 24 and opp_q1_def <= 24:
        base -= 0.5
        parts.append("Q1 mismatch against us")

    our_q4_for = us.get("q4_avg_for", 0) or 0
    opp_q4_def = them.get("q4_avg_against", 0) or 0
    if our_q4_for >= 27 and opp_q4_def >= 27:
        base += 1
        parts.append("Q4 closing edge")
    elif our_q4_for <= 22 and opp_q4_def <= 22:
        base -= 0.5
        parts.append("Q4 stalls")

    note = ", ".join(parts) if parts else "neutral quarter rhythm"
    return _clamp(base), note


def score_bench_diff(game: dict, side: str) -> tuple:
    """NBA second-unit minutes. Reads profile.bench_ppg_l5 for both sides.
    Marks unavailable upstream when not populated.
    Score = 5.0 + ((our_bench - opp_bench) / 5).
    """
    opp_side = "away" if side == "home" else "home"
    us = (game.get(f"{side}_profile", {}) or {}).get("bench_ppg_l5")
    them = (game.get(f"{opp_side}_profile", {}) or {}).get("bench_ppg_l5")
    if us is None or them is None:
        return 5.0, "no bench data"
    diff = float(us) - float(them)
    score = 5.0 + (diff / 5.0)
    return _clamp(score), f"bench L5: us {us} / them {them} ({diff:+.1f})"


# ─── NBA Extended Variables ──────────────────────────────────────────────────

def score_three_pt_rate(profile: dict, opp: dict) -> tuple:
    ppg = profile.get("ppg_L5", 0)
    pace = profile.get("pace_L5", 0)
    if not ppg:
        return 5, "no PPG data"
    if ppg >= 120 and pace:
        score = 9
    elif ppg >= 115 and pace:
        score = 8
    elif ppg >= 115:
        score = 7.5
    elif ppg >= 110:
        score = 6.5
    elif ppg >= 105:
        score = 5.5
    else:
        score = 4
    opp_def = opp.get("opp_ppg_L5", 0)
    if opp_def and opp_def >= 115:
        score += 0.5
    elif opp_def and opp_def <= 105:
        score -= 0.5
    return _clamp(score), f"PPG proxy: {ppg} | pace: {pace}"


def score_b2b_fatigue(profile: dict, opp: dict) -> tuple:
    rest = profile.get("rest_days")
    if rest is None:
        return 5, "no rest data"
    if rest <= 0:
        score = 9
        label = "B2B zero rest"
    elif rest == 1:
        score = 8
        label = "B2B 1-day rest"
    elif rest == 2:
        score = 5
        label = "2 days rest"
    else:
        score = 2
        label = f"{rest}+ days rest"
    opp_rest = opp.get("rest_days")
    if opp_rest is not None and opp_rest >= 3 and rest <= 1:
        score += 0.5
        label += " vs rested opp"
    return _clamp(score), label


def score_travel_distance(profile: dict, game: dict, pick_side: str) -> tuple:
    if pick_side == "home":
        return _clamp(1), "Home game"
    road_len = profile.get("road_trip_len", 0)
    if road_len >= 5:
        score = 9
    elif road_len >= 4:
        score = 8
    elif road_len >= 3:
        score = 6.5
    elif road_len >= 2:
        score = 5
    else:
        score = 3
    return _clamp(score), f"Road trip game {road_len}"


def score_altitude(game: dict, pick_side: str) -> tuple:
    home_name = (game.get("home_team") or game.get("home", "")).lower()
    home_profile = game.get("home_profile", {})
    if home_profile:
        home_name_alt = home_profile.get("team", "").lower()
        if home_name_alt:
            home_name = home_name + " " + home_name_alt
    is_denver = "nuggets" in home_name or "denver" in home_name or "avalanche" in home_name
    if not is_denver:
        return _clamp(5), "No altitude factor"
    if pick_side == "home":
        return _clamp(2), "Home altitude advantage (Denver)"
    return _clamp(8), "Visiting Denver altitude penalty"


def score_referee_pace(game: dict) -> tuple:
    return 5, "no referee data"


def score_turnover_rate(profile: dict, opp: dict) -> tuple:
    opp_ppg_allowed = opp.get("opp_ppg_L5", 0)
    our_def = profile.get("opp_ppg_L5", 0)
    if not opp_ppg_allowed and not our_def:
        return 5, "no defensive data"
    target = opp_ppg_allowed if opp_ppg_allowed else our_def
    if target <= 100:
        score = 9
    elif target <= 105:
        score = 8
    elif target <= 108:
        score = 7
    elif target <= 112:
        score = 5.5
    elif target <= 115:
        score = 4
    else:
        score = 3
    return _clamp(score), f"OPP allows L5: {opp_ppg_allowed} | our def: {our_def}"


# ─── Sport-Specific Variables ──────────────────────────────────────────────────

# MLB pitcher tier — derived from REAL MLB Stats API ERA + IP, not a
# hardcoded reputation list. There is no such thing as an "ace pitcher" by
# name; there is a pitcher whose current-season ERA over a meaningful sample
# says he is pitching like one. Skenes is "ace" because 2.39 ERA over 30+ IP,
# not because someone wrote him down. Tonight's kill of KNOWN_ACE_PITCHERS.
# Kept as an empty dict for any legacy import that still expects the symbol.
KNOWN_ACE_PITCHERS: dict = {}

PITCHER_TIER_VALUES = {"ace": 3.0, "good": 1.5, "unknown": 0.0, "bad": -2.0}


def _pitcher_tier_from_stats(sp: dict) -> str:
    """Classify a starting pitcher from real MLB Stats API numbers.

    Bands (current-season SP, industry-standard):
        ERA <= 3.00 + IP >= 30  -> ace
        ERA <= 3.80 + IP >= 20  -> good
        ERA >= 5.00 + IP >= 20  -> bad
        otherwise (or no sample) -> unknown
    """
    if not isinstance(sp, dict):
        return "unknown"
    era_raw = sp.get("era") if sp.get("era") is not None else sp.get("ERA")
    ip_raw = sp.get("ip") if sp.get("ip") is not None else sp.get("IP")
    if era_raw is None:
        return "unknown"
    try:
        era = float(era_raw)
        ip = float(ip_raw) if ip_raw is not None else 0.0
    except (TypeError, ValueError):
        return "unknown"
    if ip < 20:
        return "unknown"
    if era <= 3.00 and ip >= 30:
        return "ace"
    if era <= 3.80:
        return "good"
    if era >= 5.00:
        return "bad"
    return "unknown"


def _pitcher_tier_lookup(sp_or_name) -> str:
    """Backwards-compatible shim. Accepts either an sp dict (preferred) or
    a bare name string (legacy). Name-only callers always get "unknown" now
    because there is no name-based lookup table anymore."""
    if isinstance(sp_or_name, dict):
        return _pitcher_tier_from_stats(sp_or_name)
    return "unknown"


# Hitter-friendly parks (boost offense for hitters, hurt pitchers)
HITTER_FRIENDLY_PARKS_GE = {
    "Colorado Rockies", "Cincinnati Reds", "Texas Rangers",
    "New York Yankees", "Boston Red Sox", "Philadelphia Phillies",
}

# Park factors — FanGraphs 3-year park factor (100 = neutral, >100 = hitter
# friendly, <100 = pitcher friendly). Keyed by team display name as it
# appears in our ESPN/Odds data layer. Used by score_park_factor and the
# COORS_OVER chain. Updated for 2026 season; refresh annually.
PARK_FACTORS = {
    "Colorado Rockies":      112,  # Coors Field — most extreme hitter park
    "Cincinnati Reds":       105,  # Great American Ball Park
    "Texas Rangers":         104,  # Globe Life Field
    "Philadelphia Phillies": 104,  # Citizens Bank Park
    "Fenway Park":           103,  # placeholder if mapped by stadium name
    "Boston Red Sox":        103,  # Fenway Park
    "New York Yankees":      103,  # Yankee Stadium
    "Chicago Cubs":          102,  # Wrigley Field
    "Atlanta Braves":        102,  # Truist Park
    "Baltimore Orioles":     102,  # Camden Yards
    "Arizona Diamondbacks":  101,  # Chase Field
    "Toronto Blue Jays":     101,  # Rogers Centre
    "Milwaukee Brewers":     101,  # American Family Field
    "Pittsburgh Pirates":    100,  # PNC Park (neutral)
    "Detroit Tigers":        100,  # Comerica Park
    "Houston Astros":        100,  # Minute Maid Park
    "Washington Nationals":   99,  # Nationals Park
    "New York Mets":          99,  # Citi Field
    "Minnesota Twins":        99,  # Target Field
    "Cleveland Guardians":    99,  # Progressive Field
    "St. Louis Cardinals":    98,  # Busch Stadium
    "Chicago White Sox":      98,  # Guaranteed Rate Field
    "Kansas City Royals":     98,  # Kauffman Stadium
    "Los Angeles Angels":     97,  # Angel Stadium
    "Los Angeles Dodgers":    97,  # Dodger Stadium
    "Athletics":              96,  # Sutter Health Park (Sacramento)
    "San Francisco Giants":   96,  # Oracle Park
    "Seattle Mariners":       95,  # T-Mobile Park
    "Miami Marlins":          94,  # LoanDepot Park
    "San Diego Padres":       94,  # Petco Park
    "Tampa Bay Rays":         92,  # Tropicana Field — most extreme pitcher park
}


def score_park_factor(game: dict, side: str) -> tuple:
    """Score the home park's offensive bias for the picking side.

    Park factor is a SIDE signal not just a totals signal — a hitter-friendly
    park advantages a strong-hitting team picking the run line, and a
    pitcher-friendly park advantages a strong-pitching team picking the win.
    Returns (score, note). Score 5.0 = neutral.
    """
    home_team = game.get("homeTeam", "") or game.get("home_team", "")
    pf = PARK_FACTORS.get(home_team)
    if pf is None:
        return 5.0, "park factor: unknown park"

    profile = game.get(f"{side}_profile", {}) or {}
    sp = profile.get("starting_pitcher", {}) or {}
    sp_tier = _pitcher_tier_from_stats(sp)
    ppg_l5 = profile.get("ppg_L5", 0) or 0

    # Hitter-friendly park (>= 105) — strong boost for offense
    if pf >= 105:
        if ppg_l5 >= 5.0:
            return 8.5, f"hitter-friendly park ({pf}) + L5 offense {ppg_l5}"
        return 6.5, f"hitter-friendly park ({pf})"

    # Mildly hitter friendly (102-104)
    if pf >= 102:
        if ppg_l5 >= 5.0:
            return 6.5, f"mildly hitter-friendly park ({pf}) + L5 offense {ppg_l5}"
        return 5.5, f"mildly hitter-friendly park ({pf})"

    # Mildly pitcher friendly (96-98)
    if 96 <= pf <= 98:
        if side == "home" and sp_tier in ("ace", "good"):
            return 6.5, f"mildly pitcher-friendly park ({pf}) + {sp_tier} home starter"
        return 5.0, f"mildly pitcher-friendly park ({pf})"

    # Strongly pitcher friendly (<= 95)
    if pf <= 95:
        if side == "home" and sp_tier == "ace":
            return 8.0, f"pitcher-friendly park ({pf}) + ACE home starter"
        if side == "home" and sp_tier == "good":
            return 7.0, f"pitcher-friendly park ({pf}) + good home starter"
        return 4.0, f"pitcher-friendly park ({pf}) — offense suppressed"

    # 99-101 = neutral
    return 5.0, f"neutral park ({pf})"


# MLB plate umpire K%/BB% tendencies — public dataset compiled from
# Umpire Auditor / Baseball Savant. Refresh annually. Anchored at league
# average K% ~22.5, BB% ~8.4. Names match StatsAPI officials displayName.
UMPIRE_TENDENCIES = {
    # High-K umps (favor pitchers)
    "Angel Hernandez":    {"k_pct": 24.1, "bb_pct": 7.8},
    "Doug Eddings":       {"k_pct": 23.8, "bb_pct": 7.6},
    "Ron Kulpa":          {"k_pct": 23.6, "bb_pct": 8.2},
    "Mark Wegner":        {"k_pct": 23.5, "bb_pct": 8.0},
    "Marvin Hudson":      {"k_pct": 23.4, "bb_pct": 7.9},
    "C.B. Bucknor":       {"k_pct": 23.4, "bb_pct": 8.5},
    "Larry Vanover":      {"k_pct": 23.3, "bb_pct": 8.1},
    "Hunter Wendelstedt": {"k_pct": 23.3, "bb_pct": 8.0},
    "Vic Carapazza":      {"k_pct": 23.2, "bb_pct": 8.3},
    "Tony Randazzo":      {"k_pct": 23.1, "bb_pct": 8.0},
    "Bill Welke":         {"k_pct": 23.1, "bb_pct": 8.4},
    "Jansen Visconti":    {"k_pct": 23.0, "bb_pct": 8.2},
    "Sean Barber":        {"k_pct": 22.9, "bb_pct": 8.5},
    "Phil Cuzzi":         {"k_pct": 22.8, "bb_pct": 8.7},
    # League-average umps (~22.5 K%)
    "Andy Fletcher":      {"k_pct": 22.6, "bb_pct": 8.3},
    "Chris Conroy":       {"k_pct": 22.6, "bb_pct": 8.5},
    "Ed Hickox":          {"k_pct": 22.5, "bb_pct": 8.4},
    "Greg Gibson":        {"k_pct": 22.5, "bb_pct": 8.4},
    "Adrian Johnson":     {"k_pct": 22.5, "bb_pct": 8.6},
    "Will Little":        {"k_pct": 22.4, "bb_pct": 8.5},
    "Mike Estabrook":     {"k_pct": 22.4, "bb_pct": 8.7},
    "Jordan Baker":       {"k_pct": 22.3, "bb_pct": 8.5},
    "Tripp Gibson":       {"k_pct": 22.3, "bb_pct": 8.6},
    "Pat Hoberg":         {"k_pct": 22.3, "bb_pct": 8.4},
    "Cory Blaser":        {"k_pct": 22.2, "bb_pct": 8.5},
    "Brian Knight":       {"k_pct": 22.2, "bb_pct": 8.6},
    "Stu Scheurwater":    {"k_pct": 22.1, "bb_pct": 8.5},
    "Carlos Torres":      {"k_pct": 22.1, "bb_pct": 8.7},
    "Quinn Wolcott":      {"k_pct": 22.0, "bb_pct": 8.5},
    "Dan Iassogna":       {"k_pct": 22.0, "bb_pct": 8.4},
    "Manny Gonzalez":     {"k_pct": 22.0, "bb_pct": 8.6},
    # Low-K umps (favor hitters)
    "Joe West":           {"k_pct": 21.8, "bb_pct": 8.9},  # retired but cached
    "Lance Barrett":      {"k_pct": 21.8, "bb_pct": 9.0},
    "Bruce Dreckman":     {"k_pct": 21.7, "bb_pct": 9.1},
    "Alan Porter":        {"k_pct": 21.6, "bb_pct": 8.9},
    "James Hoye":         {"k_pct": 21.6, "bb_pct": 9.0},
    "Nic Lentz":          {"k_pct": 21.5, "bb_pct": 8.9},
    "John Tumpane":       {"k_pct": 21.4, "bb_pct": 9.0},
    "Bill Miller":        {"k_pct": 21.3, "bb_pct": 9.1},
    "Mike Muchlinski":    {"k_pct": 21.3, "bb_pct": 9.0},
    "Junior Valentine":   {"k_pct": 21.2, "bb_pct": 9.1},
    "Mark Carlson":       {"k_pct": 21.1, "bb_pct": 9.2},
    "Brian O'Nora":       {"k_pct": 21.0, "bb_pct": 8.9},
    "Tom Hallion":        {"k_pct": 20.9, "bb_pct": 9.0},
    "Laz Diaz":           {"k_pct": 20.8, "bb_pct": 9.2},
    "Lance Barksdale":    {"k_pct": 20.7, "bb_pct": 9.0},
    "Brian Gorman":       {"k_pct": 20.6, "bb_pct": 9.3},
}

LEAGUE_AVG_K_PCT = 22.5
LEAGUE_AVG_BB_PCT = 8.4


def score_umpire(game: dict, side: str) -> tuple:
    """Score the impact of the home plate umpire's K% / BB% tendency on the
    picking team. A high-K ump favors strong pitching teams (boost pitcher
    side); a low-K ump favors strong hitting teams.

    Reads game.umpire which is populated by data_fetch_mlb._fetch_sync from
    StatsAPI gameData.officials. Returns (score, note).
    """
    ump = game.get("umpire") or {}
    name = ump.get("name", "")
    if not name:
        return 5.0, "no umpire data"

    tend = UMPIRE_TENDENCIES.get(name)
    if not tend:
        return 5.0, f"umpire {name} (unknown tendency)"

    k_pct = tend["k_pct"]
    k_delta = k_pct - LEAGUE_AVG_K_PCT  # positive = high-K ump

    profile = game.get(f"{side}_profile", {}) or {}
    sp = profile.get("starting_pitcher", {}) or {}
    sp_tier = _pitcher_tier_from_stats(sp)

    # High-K ump (>22.8) + ace/good pitcher on the picking side = boost
    # Low-K ump (<22.2) + strong offense (ppg_L5 >= 5) = boost
    if k_delta >= 0.5 and sp_tier in ("ace", "good"):
        return 7.5, f"{name} K% {k_pct} (high-K) + {sp_tier} starter"
    if k_delta <= -0.5:
        ppg = profile.get("ppg_L5", 0) or 0
        if ppg >= 5.0:
            return 7.0, f"{name} K% {k_pct} (low-K) + L5 offense {ppg}"
        return 5.5, f"{name} K% {k_pct} (low-K)"
    if k_delta >= 0.5:
        return 6.0, f"{name} K% {k_pct} (high-K)"
    return 5.0, f"{name} K% {k_pct} (neutral)"


def score_lineup_vs_hand(game: dict, side: str) -> tuple:
    """Score the picking team's offensive matchup vs the opposing starter's
    handedness. Reads profile.lineup_vs_hand which is populated by
    data_fetch_mlb._extract_team_splits_vs_hand.

    Anchors at .720 OPS = neutral 5.0. Each .020 OPS difference moves the
    score by ~1 point. Returns (score, note).
    """
    profile = game.get(f"{side}_profile", {}) or {}
    splits = profile.get("lineup_vs_hand") or {}
    if not splits or splits.get("ops_vs_hand") is None:
        return 5.0, "no lineup vs hand splits"

    ops = splits.get("ops_vs_hand", 0.720)
    hand = splits.get("vs_hand", "?")
    avg = splits.get("avg_vs_hand")
    hr = splits.get("hr_vs_hand")

    # OPS .720 = neutral 5.0, each .020 above moves +1
    score = 5.0 + (ops - 0.720) * 50

    note_parts = [f"OPS {ops:.3f} vs {hand}HP"]
    if avg is not None:
        note_parts.append(f"AVG .{int(avg*1000):03d}")
    if hr is not None:
        note_parts.append(f"{hr} HR")
    return _clamp(score), " ".join(note_parts)


def score_bullpen(game: dict, side: str) -> tuple:
    """Score MLB bullpen quality + freshness from MLB Stats API L7 walk.

    Reads profile.bullpen which is populated by data_fetch_mlb._extract_bullpen_stats
    and contains: bullpen_era_L7, bullpen_ip_L7, bullpen_tired_arms,
    bullpen_relief_games, team_era_season.

    Returns (score, note). Score 5.0 = neutral, lower for tired/bad bullpens,
    higher for fresh/elite bullpens.
    """
    profile = game.get(f"{side}_profile", {}) or {}
    bp = profile.get("bullpen") or {}
    if not bp or "bullpen_era_L7" not in bp:
        return 5.0, "no bullpen data"

    era_L7 = bp.get("bullpen_era_L7", 4.00)
    tired = bp.get("bullpen_tired_arms", 0)
    season_era = bp.get("team_era_season")

    # Score from L7 ERA: lower = better. Anchor 4.00 = neutral 5.0.
    # Each 0.5 ERA difference moves score by ~1 point.
    score = 5.0 + (4.00 - era_L7) * 2.0
    # Penalty for tired arms (3+ appearances in 7 days)
    if tired >= 3:
        score -= 1.5
    elif tired >= 2:
        score -= 0.75
    # Bonus when L7 ERA is significantly better than season ERA (heating up)
    if season_era and era_L7 < season_era - 0.75:
        score += 0.5
    # Penalty when L7 ERA is significantly worse than season (slumping)
    if season_era and era_L7 > season_era + 0.75:
        score -= 0.5

    note = f"bullpen ERA L7 {era_L7}"
    if tired:
        note += f", {tired} tired arm{'s' if tired != 1 else ''}"
    if season_era:
        note += f" (season {season_era})"
    return _clamp(score), note


# Sentinel prefix in the note so grade_game can mark this variable unavailable
_SP_PROXY_NOTE_PREFIX = "SP unknown"


def score_starting_pitcher(game: dict, side: str) -> tuple:
    """Score MLB starting pitcher. Tier (Skenes/Skubal/etc.) is the primary
    driver — ERA differential is a tiebreaker bonus, margin proxy is the
    last resort and marks itself unavailable via note prefix so the engine
    knows not to trust it.
    """
    sp = game.get(f"{side}_profile", {}).get("starting_pitcher", {}) or {}
    opp_sp = game.get(f"{'away' if side == 'home' else 'home'}_profile", {}).get("starting_pitcher", {}) or {}

    our_name = sp.get("name", "")
    opp_name = opp_sp.get("name", "")
    our_tier = _pitcher_tier_from_stats(sp)
    opp_tier = _pitcher_tier_from_stats(opp_sp)
    our_val = PITCHER_TIER_VALUES[our_tier]
    opp_val = PITCHER_TIER_VALUES[opp_tier]

    # Primary driver: tier delta (Skenes vs unknown = +3.0 → score 8.0)
    if our_tier != "unknown" or opp_tier != "unknown":
        delta = our_val - opp_val
        score = _clamp(5 + delta)
        # ERA bonus (small) when both ERAs available
        era = sp.get("era") or sp.get("ERA")
        opp_era = opp_sp.get("era") or opp_sp.get("ERA")
        if era and opp_era:
            try:
                era_diff = float(opp_era) - float(era)
                score = _clamp(score + era_diff * 0.3)
            except (ValueError, TypeError):
                pass
        # Park penalty: pitcher at hitter-friendly park
        home_team = game.get("homeTeam", "")
        if side == "home" and home_team in HITTER_FRIENDLY_PARKS_GE:
            score = _clamp(score - 0.5)
        return score, f"SP tier: {our_name or '?'} ({our_tier}) vs {opp_name or '?'} ({opp_tier})"

    # Last resort: margin proxy. Read CORRECT field name (L5_margin, not
    # margin_L5 — old bug). Note prefix marks this as unavailable.
    profile = game.get(f"{side}_profile", {}) or {}
    margin = profile.get("L5_margin", profile.get("margin_L5", 0)) or 0
    try:
        margin = float(margin)
    except (ValueError, TypeError):
        margin = 0.0
    return _clamp(5 + margin / 3), f"{_SP_PROXY_NOTE_PREFIX} ({our_name or 'TBD'} vs {opp_name or 'TBD'}) — proxy from L5 margin {margin:+.1f}"


# Modern MLB add-ons: starter depth and pitcher-vs-lineup archetype.
def score_starter_depth(game: dict, side: str) -> tuple:
    """Modern MLB starter depth signal.

    Lower emphasis on name/tier; higher emphasis on inning capacity and
    command (BB/9) so bullpen exposure is modeled directly.
    """
    sp = game.get(f"{side}_profile", {}).get("starting_pitcher", {}) or {}
    opp_side = "away" if side == "home" else "home"
    opp_sp = game.get(f"{opp_side}_profile", {}).get("starting_pitcher", {}) or {}

    def _depth_score(p: dict) -> float:
        ip_raw = p.get("ip")
        if ip_raw is None:
            return 5.0
        try:
            ip = float(ip_raw)
        except (TypeError, ValueError):
            return 5.0
        score = 5.0
        if ip >= 100:
            score += 2.0
        elif ip >= 60:
            score += 1.25
        elif ip >= 30:
            score += 0.5
        elif ip < 20:
            score -= 0.75

        k9_raw = p.get("k9")
        bb9_raw = p.get("bb9")
        try:
            if k9_raw is not None and float(k9_raw) >= 9.5:
                score += 0.5
        except (TypeError, ValueError):
            pass
        try:
            bb9 = float(bb9_raw) if bb9_raw is not None else None
            if bb9 is not None:
                if bb9 <= 2.2:
                    score += 0.6
                elif bb9 >= 3.6:
                    score -= 0.8
        except (TypeError, ValueError):
            pass
        return score

    ours = _depth_score(sp)
    opp = _depth_score(opp_sp)
    score = _clamp(5.0 + (ours - opp) * 0.8)
    return score, f"starter depth {ours:.1f} vs {opp:.1f}"


def score_pitcher_hitter_archetype(game: dict, side: str) -> tuple:
    """Pitcher archetype vs opposing lineup archetype.

    True pitch-mix (FB/CB/SL usage) is not available in current ingest.
    Proxy with:
    - Pitcher shape: K/9 + BB/9 (power/contact/wild)
    - Opp lineup shape vs hand: AVG + HR + OPS (contact/power)
    """
    profile = game.get(f"{side}_profile", {}) or {}
    opp_side = "away" if side == "home" else "home"
    opp_profile = game.get(f"{opp_side}_profile", {}) or {}

    sp = profile.get("starting_pitcher", {}) or {}
    opp_splits = opp_profile.get("lineup_vs_hand") or {}
    k9 = sp.get("k9")
    bb9 = sp.get("bb9")
    avg = opp_splits.get("avg_vs_hand")
    hr = opp_splits.get("hr_vs_hand")
    ops = opp_splits.get("ops_vs_hand")
    if k9 is None or avg is None or hr is None:
        return 5.0, "no pitcher-vs-lineup archetype data"

    try:
        k9f = float(k9)
        bb9f = float(bb9) if bb9 is not None else 2.9
        avgf = float(avg)
        hri = int(hr)
        opsf = float(ops) if ops is not None else 0.720
    except (TypeError, ValueError):
        return 5.0, "no pitcher-vs-lineup archetype data"

    if k9f >= 9.5:
        p_type = "power"
    elif k9f <= 7.2:
        p_type = "contact"
    else:
        p_type = "balanced"

    if hri >= 40 or (opsf >= 0.760 and avgf < 0.250):
        l_type = "power"
    elif avgf >= 0.260 and hri <= 30:
        l_type = "contact"
    else:
        l_type = "balanced"

    score = 5.0
    if p_type == "power" and l_type == "power":
        score += 1.0
    elif p_type == "contact" and l_type == "power":
        score -= 1.1
    elif p_type == "power" and l_type == "contact":
        score += 0.4
    elif p_type == "contact" and l_type == "contact":
        score += 0.2

    if bb9f <= 2.2:
        score += 0.4
    elif bb9f >= 3.6:
        score -= 0.7

    return _clamp(score), f"{p_type} arm (K9 {k9f:.1f}, BB9 {bb9f:.1f}) vs {l_type} lineup (AVG {avgf:.3f}, HR {hri})"


def score_lineup_dna(game: dict, side: str) -> tuple:
    """Classify lineup as POWER, CONTACT, or BALANCED using batting splits.

    POWER = high HR count + high OPS but lower AVG (swing big, miss big).
    CONTACT = low K proxy (high AVG) + moderate OPS.
    BALANCED = everything else.
    Returns (score, note). POWER=8, CONTACT=3, BALANCED=5.
    """
    profile = game.get(f"{side}_profile", {}) or {}
    splits = profile.get("lineup_vs_hand") or {}
    if not splits:
        return 5.0, "no lineup DNA data"

    ops = splits.get("ops_vs_hand")
    avg = splits.get("avg_vs_hand")
    hr = splits.get("hr_vs_hand")
    if ops is None and avg is None:
        return 5.0, "no lineup DNA data"

    try:
        ops_f = float(ops) if ops is not None else 0.720
        avg_f = float(avg) if avg is not None else 0.250
        hr_i = int(hr) if hr is not None else 0
    except (TypeError, ValueError):
        return 5.0, "no lineup DNA data"

    if hr_i >= 35 or (ops_f >= 0.770 and avg_f < 0.255):
        return _clamp(8.0), f"POWER lineup (OPS {ops_f:.3f}, AVG {avg_f:.3f}, HR {hr_i})"
    if avg_f >= 0.265 and ops_f < 0.740 and hr_i <= 25:
        return _clamp(3.0), f"CONTACT lineup (OPS {ops_f:.3f}, AVG {avg_f:.3f}, HR {hr_i})"
    return _clamp(5.0), f"BALANCED lineup (OPS {ops_f:.3f}, AVG {avg_f:.3f}, HR {hr_i})"


def score_pitcher_profile(game: dict, side: str) -> tuple:
    """Is the starter a deep-starter (6+ IP regularly) or short-stint?

    Uses starter's season IP to estimate average depth per start.
    Deep starter (avg IP/start >= 6) = 8, committee (<= 4.5) = 3, average = 5.
    Returns (score, note).
    """
    sp = game.get(f"{side}_profile", {}).get("starting_pitcher", {}) or {}
    ip_raw = sp.get("ip")
    if ip_raw is None:
        return 5.0, "no pitcher profile data"

    try:
        ip = float(ip_raw)
    except (TypeError, ValueError):
        return 5.0, "no pitcher profile data"

    if ip < 10:
        return 5.0, f"pitcher profile: too few IP ({ip})"

    era_raw = sp.get("era")
    try:
        era = float(era_raw) if era_raw is not None else None
    except (TypeError, ValueError):
        era = None

    games_est = max(1, ip / 5.5)
    avg_depth = ip / games_est

    if avg_depth >= 6.0:
        score = 8.0
        label = "deep starter"
    elif avg_depth <= 4.5:
        score = 3.0
        label = "short stint"
    else:
        score = 5.0
        label = "average depth"

    if era is not None and era <= 3.00 and ip >= 30:
        score += 0.5
    elif era is not None and era >= 5.00:
        score -= 0.5

    note = f"{label} ({ip} IP"
    if era is not None:
        note += f", ERA {era:.2f}"
    note += ")"
    return _clamp(score), note


def score_bullpen_fatigue(game: dict, side: str) -> tuple:
    """Score bullpen fatigue from recent usage. Reads profile.bullpen L7 data.

    Heavy usage (high tired arms + high L7 IP) = low score (fatigued).
    Fresh bullpen = high score (advantage).
    Returns (score, note).
    """
    profile = game.get(f"{side}_profile", {}) or {}
    bp = profile.get("bullpen") or {}
    if not bp or "bullpen_era_L7" not in bp:
        return 5.0, "no bullpen fatigue data"

    era_l7 = bp.get("bullpen_era_L7", 4.00)
    tired = bp.get("bullpen_tired_arms", 0)
    ip_l7 = bp.get("bullpen_ip_L7", 0)
    season_era = bp.get("team_era_season")

    score = 5.0
    if tired >= 4:
        score = 2.5
    elif tired >= 3:
        score = 3.5
    elif tired >= 2:
        score = 4.0
    elif tired <= 0:
        score = 7.0
    else:
        score = 5.5

    if era_l7 > 5.00:
        score -= 1.0
    elif era_l7 > 4.50:
        score -= 0.5
    elif era_l7 < 3.00:
        score += 1.0
    elif era_l7 < 3.50:
        score += 0.5

    if season_era and era_l7 > season_era + 1.0:
        score -= 0.5

    note = f"bullpen fatigue: {tired} tired arm{'s' if tired != 1 else ''}, ERA L7 {era_l7}"
    if ip_l7:
        note += f", {ip_l7} IP L7"
    return _clamp(score), note


def score_weather_factor(game: dict, side: str) -> tuple:
    """Score weather impact on offense. Wind blowing out + warm = high (8-9).
    Cold + wind blowing in = low (2-3). Moderate/dome = neutral 5.

    Reads game.weather dict from StatsAPI. Returns (score, note).
    """
    wx = game.get("weather") or {}
    if not wx:
        return 5.0, "no weather data"

    temp_raw = wx.get("temp")
    wind_raw = wx.get("wind", "") or ""
    condition = wx.get("condition", "") or ""

    try:
        temp = int(temp_raw) if temp_raw is not None else None
    except (TypeError, ValueError):
        temp = None

    wind_lower = wind_raw.lower()
    wind_out = "out" in wind_lower
    wind_in = " in" in wind_lower or wind_lower.startswith("in ")

    wind_mph = 0
    for part in wind_lower.replace(",", " ").split():
        try:
            wind_mph = int(part)
            break
        except ValueError:
            continue

    score = 5.0

    if temp is not None:
        if temp >= 85:
            score += 1.0
        elif temp >= 75:
            score += 0.5
        elif temp <= 45:
            score -= 1.5
        elif temp <= 55:
            score -= 0.5

    if wind_out and wind_mph >= 10:
        score += 1.5
    elif wind_out and wind_mph >= 5:
        score += 0.75
    elif wind_in and wind_mph >= 10:
        score -= 1.5
    elif wind_in and wind_mph >= 5:
        score -= 0.75

    if "dome" in condition.lower() or "roof closed" in condition.lower():
        score = 5.0

    parts = []
    if temp is not None:
        parts.append(f"{temp}F")
    if wind_raw:
        parts.append(wind_raw)
    if condition:
        parts.append(condition)
    note = "weather: " + ", ".join(parts) if parts else "weather: unknown conditions"
    return _clamp(score), note


def score_gb_fb_ratio(game: dict, side: str) -> tuple:
    """Ground ball vs fly ball tendency proxy using pitcher K/9.

    High K/9 pitchers tend to be fly ball types (more whiffs = fewer GB).
    Low K/9 pitchers tend to be ground ball types (weak contact).
    GB-heavy (low K/9) = 8, FB-heavy (high K/9) = 3, neutral = 5.
    Returns (score, note).
    """
    sp = game.get(f"{side}_profile", {}).get("starting_pitcher", {}) or {}
    k9_raw = sp.get("k9")
    if k9_raw is None:
        return 5.0, "no GB/FB data"

    try:
        k9 = float(k9_raw)
    except (TypeError, ValueError):
        return 5.0, "no GB/FB data"

    bb9_raw = sp.get("bb9")
    try:
        bb9 = float(bb9_raw) if bb9_raw is not None else 3.0
    except (TypeError, ValueError):
        bb9 = 3.0

    if k9 <= 6.5:
        score = 8.0
        label = "GB-heavy"
    elif k9 <= 7.5:
        score = 6.5
        label = "GB-leaning"
    elif k9 >= 10.0:
        score = 3.0
        label = "FB-heavy"
    elif k9 >= 8.5:
        score = 4.0
        label = "FB-leaning"
    else:
        score = 5.0
        label = "neutral"

    if bb9 <= 2.2:
        score += 0.3
    elif bb9 >= 3.6:
        score -= 0.3

    return _clamp(score), f"{label} (K/9 {k9:.1f}, BB/9 {bb9:.1f})"


def score_plate_discipline(game: dict, side: str) -> tuple:
    """Score team plate discipline using batting profile data.

    High OPS + high AVG = disciplined approach (work counts, see pitches).
    Low AVG + high K proxy (low AVG with low OPS) = undisciplined.
    Returns (score, note).
    """
    profile = game.get(f"{side}_profile", {}) or {}
    splits = profile.get("lineup_vs_hand") or {}
    if not splits:
        return 5.0, "no plate discipline data"

    ops = splits.get("ops_vs_hand")
    avg = splits.get("avg_vs_hand")
    if ops is None and avg is None:
        return 5.0, "no plate discipline data"

    try:
        ops_f = float(ops) if ops is not None else 0.720
        avg_f = float(avg) if avg is not None else 0.250
    except (TypeError, ValueError):
        return 5.0, "no plate discipline data"

    disc_score = (ops_f - 0.720) * 30 + (avg_f - 0.250) * 40
    score = 5.0 + disc_score

    if ops_f >= 0.780 and avg_f >= 0.260:
        label = "disciplined"
    elif ops_f <= 0.680 or avg_f <= 0.230:
        label = "undisciplined"
    else:
        label = "average discipline"

    return _clamp(score), f"{label} (OPS {ops_f:.3f}, AVG {avg_f:.3f})"


# Hardcoded elite/good NHL goalies — fallback when SV% data not available.
# Names lowercased for matching; check by last name.
ELITE_NHL_GOALIES = {
    "hellebuyck", "sorokin", "vasilevskiy", "shesterkin", "bobrovsky",
    "saros", "markstrom", "oettinger", "hill", "kuemper", "swayman",
    "ullmark", "skinner", "demko", "hart", "gibson", "talbot", "stolarz",
}
GOOD_NHL_GOALIES = {
    "andersen", "husso", "husarek", "mrazek", "binnington", "georgiev",
    "jarry", "blackwood", "vanecek", "lyon", "merzlikins", "kahkonen",
    "wedgewood", "samsonov", "knight", "varlamov", "luukkonen",
}


def _goalie_tier(name: str) -> str | None:
    if not name:
        return None
    last = name.strip().lower().split()[-1]
    if last in ELITE_NHL_GOALIES:
        return "ELITE"
    if last in GOOD_NHL_GOALIES:
        return "GOOD"
    return None


def _normalize_sv_pct(val) -> float | None:
    """Normalize a SV% value into a 0-1 fraction, or None if junk."""
    if val is None:
        return None
    try:
        s = float(val)
    except (ValueError, TypeError):
        return None
    if s > 1.5:
        s /= 100.0
    if 0.80 <= s <= 1.0:
        return s
    return None


def score_starting_goalie(game: dict, side: str) -> tuple:
    """NHL goalie scorer — tier-first, SV% bonus on top.

    Mirrors the MLB pitcher template (commit d707fc8): tier delta is the
    primary signal, SV% is a small modifier. Returns (score, note).
    Score ladder:
      ELITE  -> 8.5 base
      GOOD   -> 7.0 base
      UNKNOWN-> 5.0 base
    SV% modifier on OUR goalie:
      > .920 -> +0.5
      > .910 -> +0.25
      < .890 -> -0.5
    Then add +/- 1.5 for the opponent tier delta so this variable is a
    relative matchup score, not just a solo grade.
    """
    profile = game.get(f"{side}_profile", {}) or {}
    opp_profile = game.get(f"{'away' if side == 'home' else 'home'}_profile", {}) or {}
    g = profile.get("starting_goalie") or {}
    opp_g = opp_profile.get("starting_goalie") or {}

    our_name = g.get("name") or profile.get("recent_starter") or profile.get("goalie")
    opp_name = opp_g.get("name") or opp_profile.get("recent_starter") or opp_profile.get("goalie")

    if not our_name and not opp_name:
        return 5, "No goalie data"

    tier_base = {"ELITE": 8.5, "GOOD": 7.0, None: 5.0}
    our_tier = _goalie_tier(our_name) if our_name else None
    opp_tier = _goalie_tier(opp_name) if opp_name else None

    score = tier_base[our_tier]

    # SV% bonus on our goalie (tier ladder remains primary)
    our_sv = _normalize_sv_pct(g.get("sv_pct") or g.get("SV%") or g.get("svp"))
    opp_sv = _normalize_sv_pct(opp_g.get("sv_pct") or opp_g.get("SV%") or opp_g.get("svp"))
    if our_sv is not None:
        if our_sv > 0.920:
            score += 0.5
        elif our_sv > 0.910:
            score += 0.25
        elif our_sv < 0.890:
            score -= 0.5

    # Opponent delta (half weight so tier remains primary)
    score += (tier_base[our_tier] - tier_base[opp_tier]) * 0.3

    our_label = our_tier or "UNKNOWN"
    opp_label = opp_tier or "UNKNOWN"
    our_sv_txt = f" {our_sv:.3f}" if our_sv is not None else ""
    opp_sv_txt = f" {opp_sv:.3f}" if opp_sv is not None else ""
    note = (f"Goalie: {our_name or '?'} ({our_label}{our_sv_txt}) "
            f"vs {opp_name or '?'} ({opp_label}{opp_sv_txt})")
    return _clamp(score), note


# ─── Soccer Hardcoded Knowledge ───────────────────────────────────────────────
# Top scorer / key creator per top-flight club. Keyed by lowercased team
# displayName / shortDisplayName (both variants matched). Values are
# lowercase last names of the primary goal-source. A single missing starter
# here (Haaland, Mbappe, Kane, Salah) is worth ~0.5-0.8 goals in the model
# and is the equivalent of an NBA star-player edge.
ELITE_SOCCER_STRIKERS = {
    # Premier League
    "manchester city": ["haaland", "de bruyne", "foden"],
    "man city": ["haaland", "de bruyne", "foden"],
    "arsenal": ["saka", "odegaard", "havertz"],
    "liverpool": ["salah", "nunez", "diaz"],
    "tottenham": ["son", "solanke", "maddison"],
    "tottenham hotspur": ["son", "solanke", "maddison"],
    "chelsea": ["palmer", "jackson", "madueke"],
    "manchester united": ["fernandes", "rashford", "hojlund"],
    "man united": ["fernandes", "rashford", "hojlund"],
    "newcastle": ["isak", "gordon", "bruno"],
    "newcastle united": ["isak", "gordon", "bruno"],
    "aston villa": ["watkins", "rogers", "mcginn"],
    "west ham": ["bowen", "kudus", "paqueta"],
    "west ham united": ["bowen", "kudus", "paqueta"],
    "brighton": ["mitoma", "joao pedro", "welbeck"],
    "brighton & hove albion": ["mitoma", "joao pedro", "welbeck"],
    "brentford": ["mbeumo", "wissa"],
    "crystal palace": ["eze", "mateta", "olise"],
    "fulham": ["muniz", "iwobi", "pereira"],
    "wolverhampton wanderers": ["cunha", "hwang", "sarabia"],
    "wolves": ["cunha", "hwang", "sarabia"],
    "nottingham forest": ["wood", "hudson-odoi", "gibbs-white"],
    "everton": ["calvert-lewin", "ndiaye", "mcneil"],
    "bournemouth": ["evanilson", "semenyo", "kluivert"],
    "ipswich town": ["delap", "hirst"],
    "leicester city": ["vardy", "mavididi"],
    "southampton": ["armstrong", "dibling"],
    # La Liga
    "real madrid": ["mbappe", "vinicius", "bellingham", "rodrygo"],
    "barcelona": ["lewandowski", "yamal", "raphinha", "pedri"],
    "atletico madrid": ["griezmann", "alvarez", "morata"],
    "atletico": ["griezmann", "alvarez", "morata"],
    "athletic club": ["williams", "guruzeta"],
    "athletic bilbao": ["williams", "guruzeta"],
    "real sociedad": ["oyarzabal", "becker", "kubo"],
    "real betis": ["isco", "bakambu", "ezzalzouli"],
    "villarreal": ["moreno", "baena", "barry"],
    "sevilla": ["romero", "rafa mir", "lukebakio"],
    "valencia": ["hugo duro", "canos"],
    "girona": ["stuani", "tsygankov", "portu"],
    # Serie A
    "inter milan": ["lautaro martinez", "thuram", "calhanoglu"],
    "inter": ["lautaro martinez", "thuram", "calhanoglu"],
    "ac milan": ["leao", "pulisic", "morata", "reijnders"],
    "milan": ["leao", "pulisic", "morata", "reijnders"],
    "juventus": ["vlahovic", "yildiz", "koopmeiners"],
    "napoli": ["lukaku", "kvaratskhelia", "mctominay", "politano"],
    "roma": ["dybala", "dovbyk", "pellegrini"],
    "as roma": ["dybala", "dovbyk", "pellegrini"],
    "lazio": ["zaccagni", "castellanos", "dia"],
    "atalanta": ["retegui", "lookman", "de ketelaere"],
    "fiorentina": ["kean", "beltran", "gudmundsson"],
    "bologna": ["orsolini", "castro", "ndoye"],
    "torino": ["zapata", "sanabria"],
    # Bundesliga
    "bayern munich": ["kane", "musiala", "sane", "olise"],
    "fc bayern munchen": ["kane", "musiala", "sane", "olise"],
    "bayer leverkusen": ["wirtz", "boniface", "schick", "frimpong"],
    "borussia dortmund": ["adeyemi", "guirassy", "brandt", "gittens"],
    "dortmund": ["adeyemi", "guirassy", "brandt", "gittens"],
    "rb leipzig": ["openda", "sesko", "olmo"],
    "eintracht frankfurt": ["marmoush", "ekitike", "uzun"],
    "vfb stuttgart": ["woltemade", "undav", "demirovic"],
    "stuttgart": ["woltemade", "undav", "demirovic"],
    "borussia monchengladbach": ["kleindienst", "hack", "honorat"],
    "werder bremen": ["ducksch", "njinmah"],
    "wolfsburg": ["wind", "majer"],
    # Ligue 1
    "paris saint-germain": ["dembele", "barcola", "kolo muani", "doue"],
    "psg": ["dembele", "barcola", "kolo muani", "doue"],
    "marseille": ["greenwood", "maupay", "rabiot"],
    "olympique marseille": ["greenwood", "maupay", "rabiot"],
    "monaco": ["ben seghir", "embolo", "balogun"],
    "lille": ["david", "zhegrova", "cabella"],
    "lyon": ["lacazette", "mikautadze", "cherki"],
    "olympique lyonnais": ["lacazette", "mikautadze", "cherki"],
    "nice": ["guessand", "boga", "moffi"],
    "strasbourg": ["emegha", "diarra"],
    # MLS
    "inter miami": ["messi", "suarez", "alba", "busquets"],
    "inter miami cf": ["messi", "suarez", "alba", "busquets"],
    "lafc": ["bouanga", "giroud"],
    "los angeles fc": ["bouanga", "giroud"],
    "la galaxy": ["pec", "paintsil", "joveljic"],
    "cincinnati": ["denkey", "acosta"],
    "fc cincinnati": ["denkey", "acosta"],
    "columbus crew": ["rossi", "cucho hernandez"],
    "seattle sounders": ["ruidiaz", "morris"],
    "seattle sounders fc": ["ruidiaz", "morris"],
    "philadelphia union": ["uhre", "carranza"],
    "new york city fc": ["martinez", "magno"],
    "atlanta united": ["silva", "almada"],
    "atlanta united fc": ["silva", "almada"],
    "portland timbers": ["moreno", "mora"],
    "new york red bulls": ["choupo-moting", "morgan"],
    "orlando city": ["torres", "pereyra"],
    "orlando city sc": ["torres", "pereyra"],
    "vancouver whitecaps": ["brian white", "gauld"],
    "vancouver whitecaps fc": ["brian white", "gauld"],
    # Liga MX
    "club america": ["henry martin", "zendejas", "rodrigo aguirre"],
    "america": ["henry martin", "zendejas", "rodrigo aguirre"],
    "chivas": ["alvarado", "pulido"],
    "guadalajara": ["alvarado", "pulido"],
    "monterrey": ["berterame", "canales", "ocampos"],
    "tigres": ["gignac", "brunetta"],
    "tigres uanl": ["gignac", "brunetta"],
    "cruz azul": ["rotondi", "sepulveda"],
    "pumas": ["dinenno", "silva"],
    "pumas unam": ["dinenno", "silva"],
}

# Team → starting goalkeeper mapping. Used to populate profile.goalkeeper
# so score_goalkeeper() can tier them. Keeper changes mid-season happen —
# update this dict when they do. Same pattern as ELITE_SOCCER_STRIKERS.
TEAM_STARTING_KEEPERS = {
    # Premier League
    "manchester city": "ederson", "man city": "ederson",
    "arsenal": "raya", "liverpool": "alisson",
    "tottenham": "vicario", "tottenham hotspur": "vicario",
    "chelsea": "sanchez", "manchester united": "onana", "man united": "onana",
    "newcastle": "pope", "newcastle united": "pope",
    "aston villa": "emi martinez", "west ham": "areola", "west ham united": "areola",
    "brighton": "verbruggen", "brighton & hove albion": "verbruggen",
    "brentford": "flekken", "crystal palace": "henderson",
    "fulham": "leno", "everton": "pickford",
    "wolves": "sa", "wolverhampton wanderers": "sa",
    "bournemouth": "kepa", "nottingham forest": "sels",
    "ipswich": "walton", "ipswich town": "walton",
    "leicester": "hermansen", "leicester city": "hermansen",
    "southampton": "ramsdale", "leeds": "meslier", "leeds united": "meslier",
    # La Liga
    "real madrid": "courtois", "barcelona": "ter stegen",
    "atletico madrid": "oblak", "real sociedad": "remiro",
    "athletic bilbao": "rulli", "athletic club": "rulli",
    "villarreal": "jorgensen", "real betis": "rui silva",
    "girona": "gazzaniga", "sevilla": "bounou",
    "valencia": "mamardashvili", "getafe": "soria",
    "celta vigo": "guaita", "rayo vallecano": "dimitrievski",
    "mallorca": "greif", "levante": "cardenas",
    # Serie A
    "inter milan": "sommer", "internazionale": "sommer",
    "ac milan": "maignan", "milan": "maignan",
    "juventus": "di gregorio", "napoli": "meret",
    "roma": "svilar", "as roma": "svilar",
    "atalanta": "carnesecchi", "lazio": "provedel",
    "fiorentina": "de gea", "bologna": "skorupski",
    "torino": "milinkovic-savic",
    # Bundesliga
    "bayern munich": "neuer", "bayern": "neuer",
    "borussia dortmund": "kobel", "dortmund": "kobel",
    "bayer leverkusen": "hradecky", "leverkusen": "hradecky",
    "rb leipzig": "gulacsi", "leipzig": "gulacsi",
    "stuttgart": "nubel", "vfb stuttgart": "nubel",
    "eintracht frankfurt": "trapp", "frankfurt": "trapp",
    # Ligue 1
    "psg": "donnarumma", "paris saint-germain": "donnarumma",
    "marseille": "de lange", "olympique marseille": "de lange",
    "monaco": "kohn", "lyon": "perri", "olympique lyonnais": "perri",
    "lille": "chevalier",
    # MLS
    "inter miami": "callender", "la galaxy": "scott",
    "lafc": "crepeau", "los angeles fc": "crepeau",
    "atlanta united": "guzan", "seattle sounders": "thomas",
    "columbus crew": "schulte", "fc cincinnati": "kann",
    # Liga MX
    "club america": "ochoa", "america": "ochoa",
    "chivas": "rangel", "guadalajara": "rangel",
    "monterrey": "andrada", "tigres": "guzman", "tigres uanl": "guzman",
    "cruz azul": "jurado",
}

# Elite / good top-flight goalkeepers. Last names (lowercase) unless a
# multi-word surname is required.
ELITE_SOCCER_KEEPERS = {
    "alisson", "courtois", "ederson", "donnarumma", "oblak", "ter stegen",
    "sommer", "onana", "maignan", "raya", "sanchez", "dibu martinez",
    "emi martinez", "emiliano martinez", "pickford", "neuer", "szczesny",
    "bounou", "lunin", "rulli", "provedel", "milinkovic-savic",
    "di gregorio", "svilar", "mamardashvili", "remiro",
}
GOOD_SOCCER_KEEPERS = {
    "kepa", "areola", "henderson", "turner", "flekken", "sels", "pope",
    "steele", "fabianski", "vicario", "meslier", "forster", "jorgensen",
    "sa", "verbruggen", "gunn", "ramsdale",
}


def _soccer_keeper_tier(name: str) -> str | None:
    if not name:
        return None
    lc = name.strip().lower()
    last = lc.split()[-1]
    for key in ELITE_SOCCER_KEEPERS:
        if key == last or lc.endswith(key):
            return "ELITE"
    for key in GOOD_SOCCER_KEEPERS:
        if key == last or lc.endswith(key):
            return "GOOD"
    return None


def _soccer_team_stars(team_name: str) -> list:
    """Return list of lowercased star last names for a soccer club, or []."""
    if not team_name:
        return []
    key = team_name.strip().lower()
    stars = ELITE_SOCCER_STRIKERS.get(key)
    if stars:
        return stars
    for suffix in (" fc", " cf", " sc", " afc"):
        if key.endswith(suffix):
            stars = ELITE_SOCCER_STRIKERS.get(key[: -len(suffix)])
            if stars:
                return stars
    for dk, v in ELITE_SOCCER_STRIKERS.items():
        if dk in key or key in dk:
            return v
    return []


def _soccer_stars_out(game: dict, side: str) -> list:
    """Return list of (player_name, status) tuples for known stars on `side`
    that appear on the ESPN injury list with OUT / DOUBTFUL / SUSPENDED."""
    team = game.get("homeTeam" if side == "home" else "awayTeam", "")
    stars = _soccer_team_stars(team)
    if not stars:
        return []
    injuries = game.get("injuries", {}).get(side, []) or []
    hits = []
    for inj in injuries:
        if inj.get("status") not in ("OUT", "DOUBTFUL", "SUSPENDED"):
            continue
        pname = (inj.get("name") or inj.get("player") or "").strip().lower()
        if not pname:
            continue
        for star in stars:
            if star in pname:
                hits.append((inj.get("name") or pname, inj.get("status")))
                break
    return hits


def score_soccer_key_player(game: dict, side: str) -> tuple:
    """Soccer-flavored star_player override. Rewards when opp has an elite
    attacker OUT, penalizes when ours is OUT. Falls back to the generic
    injury diff if no known stars are flagged."""
    our_out = _soccer_stars_out(game, side)
    opp_side = "away" if side == "home" else "home"
    opp_out = _soccer_stars_out(game, opp_side)
    if not our_out and not opp_out:
        return score_star_player(game, side)
    score = 5.0 + 2.0 * len(opp_out) - 2.0 * len(our_out)
    parts = []
    if opp_out:
        parts.append("OPP out: " + ", ".join(n for n, _ in opp_out))
    if our_out:
        parts.append("US out: " + ", ".join(n for n, _ in our_out))
    return _clamp(score), " | ".join(parts)


def score_fixture_congestion(game: dict, side: str) -> tuple:
    p = game.get(f"{side}_profile", {}) or {}
    opp = game.get(f"{'away' if side == 'home' else 'home'}_profile", {}) or {}
    # Treat 0 as a real value (not missing). Only fall through when BOTH sides
    # return None. Previously `our or ...` dropped zeros and forced a flat 5
    # for every match, and the function had no penalty branch (our > their
    # never scored below 5).
    our = p.get("matches_in_10d")
    if our is None:
        our = p.get("congestion_10d")
    their = opp.get("matches_in_10d")
    if their is None:
        their = opp.get("congestion_10d")
    if our is None and their is None:
        return 5, "No congestion data"
    try:
        our_i = int(our or 0)
        their_i = int(their or 0)
    except (ValueError, TypeError):
        return 5, "No congestion data"
    diff = their_i - our_i  # positive = opp more congested = edge for us
    if diff >= 3: return 9, f"Them:{their_i} vs Us:{our_i} in 10d (heavy legs opp)"
    if diff == 2: return 8, f"Them:{their_i} vs Us:{our_i} in 10d"
    if diff == 1: return 6.5, f"Them:{their_i} vs Us:{our_i} in 10d"
    if diff == 0: return 5, f"Even:{our_i} matches in 10d"
    if diff == -1: return 3.5, f"Them:{their_i} vs Us:{our_i} in 10d"
    if diff == -2: return 2, f"Them:{their_i} vs Us:{our_i} in 10d (heavy legs us)"
    return 1.5, f"Them:{their_i} vs Us:{our_i} in 10d (very heavy legs us)"


def score_motivation(game: dict, side: str) -> tuple:
    p = game.get(f"{side}_profile", {})
    opp = game.get(f"{'away' if side == 'home' else 'home'}_profile", {})
    our_pct = _win_pct(p.get("record"))
    opp_pct = _win_pct(opp.get("record"))
    if opp_pct < 0.35 and our_pct > 0.55:
        return 8, f"Motivation: us {our_pct:.0%} vs them {opp_pct:.0%}"
    elif our_pct < 0.35 and opp_pct > 0.55:
        return 2, f"They're motivated: {opp_pct:.0%} vs us {our_pct:.0%}"
    return _clamp(5 + (our_pct - opp_pct) * 6), f"Records: {our_pct:.0%} vs {opp_pct:.0%}"


# ─── Spread Amplifier ──────────────────────────────────────────────────────────

def _apply_spread_amplifier(composite: float, variables: dict) -> float:
    scores = sorted(
        [(v.get("score", 5), v.get("weight", 5)) for v in variables.values()],
        key=lambda x: x[0] * x[1], reverse=True
    )
    if not scores:
        return composite
    top3 = scores[:3]
    bot3 = scores[-3:]
    top3_avg = sum(s for s, _ in top3) / len(top3)
    bot3_avg = sum(s for s, _ in bot3) / len(bot3)
    if top3_avg >= 8.5:
        composite = composite * 0.8 + top3_avg * 0.2
    elif bot3_avg <= 2.5:
        composite = composite * 0.8 + bot3_avg * 0.2
    all_scores = [s for s, _ in scores]
    if min(all_scores) <= 1.5 and composite > 4.0:
        composite = min(composite, 4.0)
    return round(composite, 2)


# ─── Chain System (30+ chains) ─────────────────────────────────────────────────

CHAINS = {
    # Positive chains (+bonus)
    "THE_MISPRICING":    {"bonus": 1.0, "sports": None},
    "FATIGUE_FADE":      {"bonus": 0.8, "sports": None},
    "FORM_WAVE":         {"bonus": 0.7, "sports": None},
    "INJURY_GOLDMINE":   {"bonus": 0.8, "sports": None},
    "REST_DOMINATION":   {"bonus": 0.7, "sports": None},
    "SHARPS_LOVE":       {"bonus": 0.8, "sports": None},
    "BLOWOUT_INCOMING":  {"bonus": 0.7, "sports": ["NBA", "NCAAB"]},
    "MISMATCH_MASSACRE": {"bonus": 0.8, "sports": None},
    "ROAD_WARRIOR":      {"bonus": 0.6, "sports": None},
    "BENCH_MOB":         {"bonus": 0.5, "sports": None},
    "REVENGE_GAME":      {"bonus": 0.5, "sports": None},
    "BOUNCE_BACK":       {"bonus": 0.5, "sports": None},
    "HUNGRY_DOG":        {"bonus": 0.6, "sports": None},
    # Negative chains (-penalty)
    "DUMPSTER_FIRE":     {"bonus": -1.0, "sports": None},
    "COLD_TAKE":         {"bonus": -0.7, "sports": None},
    "GLASS_CANNON":      {"bonus": -0.5, "sports": None},
    "SCHEDULE_LOSS":     {"bonus": -0.7, "sports": None},
    "THIN_ROSTER":       {"bonus": -0.6, "sports": None},
    "COASTING_FAV":      {"bonus": -0.5, "sports": None},
    "FADE_THE_STREAK":   {"bonus": -0.5, "sports": None},
    # Sport-specific
    "GOALIE_EDGE":       {"bonus": 0.7, "sports": ["NHL"]},
    "GOALIE_WORKLOAD_WALL": {"bonus": -0.7, "sports": ["NHL"]},
    "SPECIAL_TEAMS_EDGE": {"bonus": 0.7, "sports": ["NHL"]},
    "B2B_BLEED":         {"bonus": -0.7, "sports": ["NHL"]},
    "SHOT_QUALITY_SURGE": {"bonus": 0.6, "sports": ["NHL"]},
    "BACKUP_MISMATCH":   {"bonus": 0.6, "sports": ["NHL"]},
    "SPECIAL_TEAMS_VOID": {"bonus": -0.6, "sports": ["NHL"]},
    "ALTITUDE_ICE":      {"bonus": -0.5, "sports": ["NHL"]},
    "BULLPEN_LOCKDOWN":  {"bonus": 0.8, "sports": ["MLB"]},
    "BULLPEN_FATIGUE_CASCADE": {"bonus": -0.7, "sports": ["MLB"]},
    "POWER_FLYBALL_OVER": {"bonus": 0.7, "sports": ["MLB"]},
    "CONTACT_PRESSURE":  {"bonus": 0.5, "sports": ["MLB"]},
    "GROUNDBALL_DUEL":   {"bonus": -0.6, "sports": ["MLB"]},
    "COORS_ACTUAL":      {"bonus": 0.9, "sports": ["MLB"]},
    "ACE_ISOLATION_TRAP": {"bonus": -0.6, "sports": ["MLB"]},
    "PLATOON_EXPLOIT":   {"bonus": 0.6, "sports": ["MLB"]},
    "FIVE_AND_DIVE":     {"bonus": 0.5, "sports": ["MLB"]},
    "WEATHER_WIND_BOOST": {"bonus": 0.6, "sports": ["MLB"]},
    "CONGESTION_FADE":   {"bonus": 0.8, "sports": ["SOCCER"]},
    "CLASS_GAP":         {"bonus": 0.7, "sports": ["SOCCER"]},
    "FORTRESS_HOME":     {"bonus": 0.6, "sports": ["SOCCER"]},
    "TOURIST_TRAP":      {"bonus": -0.6, "sports": ["SOCCER"]},
    "DERBY_CHAOS":       {"bonus": 0.5, "sports": ["SOCCER"]},
    "KEEPER_WALL":       {"bonus": 0.6, "sports": ["SOCCER"]},
    "ROTATION_RISK":     {"bonus": -0.6, "sports": ["SOCCER"]},
    "XG_REGRESSION":     {"bonus": 0.5, "sports": ["SOCCER"]},
    "SET_PIECE_THREAT":  {"bonus": 0.4, "sports": ["SOCCER"]},
    "EUROPEAN_HANGOVER": {"bonus": -0.5, "sports": ["SOCCER"]},
    "LEAGUE_FORTRESS":   {"bonus": 0.5, "sports": ["SOCCER"]},
    "AWAY_DAY_FADE":     {"bonus": -0.5, "sports": ["SOCCER"]},
    "BLUE_BLOOD_TRAP":   {"bonus": -0.5, "sports": ["NCAAB"]},
    "MARCH_MADNESS_UPSET": {"bonus": -0.6, "sports": ["NCAAB"]},
    "TEMPO_TRAP":        {"bonus": 0.5, "sports": ["NCAAB"]},
    "CONFERENCE_MISMATCH": {"bonus": 0.6, "sports": ["NCAAB"]},
    "HOME_COURT_CAULDRON": {"bonus": 0.5, "sports": ["NCAAB"]},
    "DEPTH_DRAIN":       {"bonus": -0.5, "sports": ["NCAAB"]},
    "TOURNAMENT_PEDIGREE": {"bonus": 0.4, "sports": ["NCAAB"]},
    "THREE_POINT_STORM": {"bonus": 0.7, "sports": ["NBA"]},
    "B2B_CORPSE":        {"bonus": -0.8, "sports": ["NBA"]},
    "ALTITUDE_BLEED":    {"bonus": -0.6, "sports": ["NBA"]},
    "PACE_MISMATCH":     {"bonus": 0.6, "sports": ["NBA"]},
    "LOAD_MANAGEMENT_ARB": {"bonus": 0.5, "sports": ["NBA"]},
    "CLUTCH_LOCK":       {"bonus": 0.5, "sports": ["NBA"]},
    "TURNOVER_PRESSURE": {"bonus": 0.5, "sports": ["NBA"]},
    "REF_PACE_BOOST":    {"bonus": 0.4, "sports": ["NBA"]},
    "WEATHER_FADE":      {"bonus": -0.7, "sports": ["NFL"]},
    "DOME_TEAM_FREEZE":  {"bonus": -0.6, "sports": ["NFL"]},
    "DIVISIONAL_DOGFIGHT": {"bonus": 0.5, "sports": ["NFL"]},
    "TURNOVER_MACHINE":  {"bonus": 0.7, "sports": ["NFL"]},
    "RED_ZONE_HAMMER":   {"bonus": 0.6, "sports": ["NFL"]},
    "PRIMETIME_LETDOWN": {"bonus": -0.5, "sports": ["NFL"]},
    "QB_WEATHER_EDGE":   {"bonus": 0.6, "sports": ["NFL"]},
    "GROUND_AND_POUND":  {"bonus": 0.5, "sports": ["NFL"]},
    "COACHING_MISMATCH": {"bonus": 0.5, "sports": ["NFL"]},
    "SCHEDULE_TRAP":     {"bonus": -0.6, "sports": ["NFL"]},
    "RECRUITING_GAP":    {"bonus": 0.7, "sports": ["NCAAF"]},
    "HOME_FORTRESS_CFB": {"bonus": 0.6, "sports": ["NCAAF"]},
    "COACHING_CHAOS":    {"bonus": -0.6, "sports": ["NCAAF"]},
    "RIVALRY_UPSET":     {"bonus": 0.5, "sports": ["NCAAF"]},
    "PORTAL_FLUX":       {"bonus": -0.5, "sports": ["NCAAF"]},
    # MMA chains
    "REACH_STRIKER":     {"bonus": 0.6, "sports": ["MMA"]},
    "GRAPPLER_TRAP":     {"bonus": 0.5, "sports": ["MMA"]},
    "CAMP_EDGE":         {"bonus": 0.4, "sports": ["MMA"]},
    "FINISH_THREAT":     {"bonus": 0.5, "sports": ["MMA"]},
    "RING_RUST":         {"bonus": -0.5, "sports": ["MMA"]},
    # Boxing chains
    "REACH_KING":        {"bonus": 0.7, "sports": ["BOXING"]},
    "SOUTHPAW_ANGLE":    {"bonus": 0.5, "sports": ["BOXING"]},
    "RING_RUST_BOX":     {"bonus": -0.6, "sports": ["BOXING"]},
    "KO_ARTIST":         {"bonus": 0.5, "sports": ["BOXING"]},
}

CHAIN_CAP = 2.0


def check_chain(name: str, v: dict) -> bool:
    """Check if chain triggers. v = {var_name: score}"""
    g = lambda k, default=0: v.get(k, default)

    if name == "THE_MISPRICING":
        return g("star_player") >= 8 and g("line_movement") <= 3
    elif name == "FATIGUE_FADE":
        return g("rest") >= 8 and g("road_trip") >= 7 and g("depth") >= 7
    elif name == "FORM_WAVE":
        return g("form") >= 8 and g("off_ranking") >= 8 and g("ats") >= 7
    elif name == "INJURY_GOLDMINE":
        return g("star_player") >= 8 and g("line_movement") <= 3 and g("form") >= 6
    elif name == "REST_DOMINATION":
        return g("rest") >= 8 and g("home_away") >= 6 and g("road_trip") >= 6
    elif name == "SHARPS_LOVE":
        return g("line_movement") >= 8 and g("form") >= 6
    elif name == "BLOWOUT_INCOMING":
        return g("off_ranking") >= 8 and g("def_ranking") >= 7 and g("home_away") >= 6
    elif name == "MISMATCH_MASSACRE":
        return g("off_ranking") >= 8 and g("def_ranking") >= 7
    elif name == "ROAD_WARRIOR":
        return g("home_away") <= 4 and g("form") >= 7 and g("rest") >= 6
    elif name == "BENCH_MOB":
        return g("depth") >= 7 and g("star_player") >= 6 and g("form") >= 6
    elif name == "REVENGE_GAME":
        return g("h2h", 10) <= 3 and g("form") >= 7 and g("home_away") >= 6
    elif name == "BOUNCE_BACK":
        return g("form", 10) <= 3 and g("off_ranking") >= 7 and g("home_away") >= 6
    elif name == "HUNGRY_DOG":
        return g("form") >= 7 and g("motivation") >= 7 and g("line_movement") >= 6
    elif name == "DUMPSTER_FIRE":
        return g("form", 10) <= 3 and g("off_ranking", 10) <= 3 and g("star_player", 10) <= 4
    elif name == "COLD_TAKE":
        avg = sum(v.values()) / len(v) if v else 5
        return avg <= 4.5
    elif name == "GLASS_CANNON":
        return g("off_ranking") >= 7 and g("def_ranking", 10) <= 3
    elif name == "SCHEDULE_LOSS":
        return g("rest", 10) <= 3 and g("road_trip", 10) <= 3 and g("form", 10) <= 4
    elif name == "THIN_ROSTER":
        return g("depth", 10) <= 3 and g("star_player", 10) <= 4
    elif name == "COASTING_FAV":
        return g("form", 10) <= 4 and g("motivation", 10) <= 4 and g("off_ranking", 10) <= 5
    elif name == "FADE_THE_STREAK":
        return g("form") >= 9 and g("home_away", 10) <= 4 and g("rest", 10) <= 4
    elif name == "GOALIE_EDGE":
        return g("goalie") >= 8 and g("def_ranking") >= 7 and g("rest") >= 6
    elif name == "GOALIE_WORKLOAD_WALL":
        if g("goalie") >= 9:
            return False
        return g("goalie_workload") >= 8 and g("rest", 10) <= 4
    elif name == "SPECIAL_TEAMS_EDGE":
        if g("form", 10) <= 3:
            return False
        return g("pp_pct") >= 8 and g("pk_pct") >= 7
    elif name == "B2B_BLEED":
        if g("home_away") >= 7:
            return False
        return g("b2b_flag") >= 8 and g("travel_fatigue") >= 7
    elif name == "SHOT_QUALITY_SURGE":
        if g("goalie", 10) <= 4:
            return False
        return g("shot_quality") >= 8 and g("off_ranking") >= 7
    elif name == "BACKUP_MISMATCH":
        if g("form", 10) <= 3:
            return False
        return g("goalie") >= 7 and g("goalie_workload", 10) <= 3
    elif name == "SPECIAL_TEAMS_VOID":
        if g("off_ranking") >= 8:
            return False
        return g("pp_pct", 10) <= 3 and g("pk_pct", 10) <= 3
    elif name == "ALTITUDE_ICE":
        if g("form") >= 8:
            return False
        return g("travel_fatigue") >= 7 and g("b2b_flag") >= 6 and g("home_away", 10) <= 4
    elif name == "BULLPEN_LOCKDOWN":
        return g("bullpen") >= 8 and g("starter_depth") <= 5 and g("pitcher_profile") <= 5
    elif name == "BULLPEN_FATIGUE_CASCADE":
        if g("off_ranking") >= 8:
            return False
        return g("bullpen_fatigue") >= 8 and g("starter_depth") <= 5
    elif name == "POWER_FLYBALL_OVER":
        if g("bullpen") >= 8:
            return False
        return g("lineup_dna") >= 8 and g("gb_fb_ratio") <= 3 and g("park_factor") >= 6
    elif name == "CONTACT_PRESSURE":
        if g("def_ranking") >= 8:
            return False
        return g("lineup_dna") <= 3 and g("plate_discipline") >= 7 and g("pitcher_hitter_archetype") <= 4
    elif name == "GROUNDBALL_DUEL":
        if g("bullpen_fatigue") >= 7:
            return False
        return g("gb_fb_ratio") >= 8 and g("def_ranking") >= 7 and g("park_factor") <= 5
    elif name == "COORS_ACTUAL":
        if g("weather_factor") <= 3:
            return False
        return g("park_factor") >= 9 and (g("lineup_dna") >= 7 or g("gb_fb_ratio") <= 3) and g("bullpen") <= 6
    elif name == "ACE_ISOLATION_TRAP":
        if g("off_ranking") >= 8:
            return False
        return g("starting_pitcher") >= 8 and g("bullpen") <= 4 and g("def_ranking") <= 5
    elif name == "PLATOON_EXPLOIT":
        if g("starter_depth") >= 8:
            return False
        return g("lineup_vs_hand") >= 9 and g("pitcher_hitter_archetype") <= 4
    elif name == "FIVE_AND_DIVE":
        if g("park_factor") <= 3:
            return False
        return g("starter_depth") <= 4 and g("bullpen") <= 5 and g("off_ranking") >= 6
    elif name == "WEATHER_WIND_BOOST":
        if g("gb_fb_ratio") >= 7:
            return False
        return g("weather_factor") >= 8 and g("lineup_dna") >= 7 and g("park_factor") >= 6
    elif name == "CONGESTION_FADE":
        return g("congestion") >= 8 and g("rest") >= 7
    elif name == "CLASS_GAP":
        return g("form") >= 8 and g("off_ranking") >= 7 and g("home_away") >= 7
    elif name == "FORTRESS_HOME":
        return g("home_away") >= 8 and g("def_ranking") >= 7 and g("form") >= 7
    elif name == "TOURIST_TRAP":
        return g("home_away", 10) <= 4 and g("congestion", 10) <= 3
    elif name == "DERBY_CHAOS":
        return g("h2h") >= 7 and g("form") >= 6 and g("motivation") >= 6
    elif name == "KEEPER_WALL":
        if g("congestion") >= 8:
            return False
        return g("goalkeeper") >= 8 and g("def_ranking") >= 7 and g("form") >= 6
    elif name == "ROTATION_RISK":
        if g("depth") >= 7:
            return False
        return g("squad_rotation") >= 8 and g("congestion") >= 7 and g("motivation", 10) <= 5
    elif name == "XG_REGRESSION":
        if g("star_player", 10) <= 3:
            return False
        return g("xg_diff") >= 8 and g("form", 10) <= 5
    elif name == "SET_PIECE_THREAT":
        if g("home_away", 10) <= 3:
            return False
        return g("set_piece") >= 8 and g("off_ranking") >= 6
    elif name == "EUROPEAN_HANGOVER":
        if g("home_away") >= 7:
            return False
        return g("congestion") >= 8 and g("squad_rotation", 10) <= 3 and g("rest", 10) <= 3
    elif name == "LEAGUE_FORTRESS":
        if g("star_player", 10) <= 3:
            return False
        return g("league_home_boost") >= 8 and g("home_away") >= 8 and g("form") >= 6
    elif name == "AWAY_DAY_FADE":
        if g("form") >= 9:
            return False
        return g("home_away", 10) <= 3 and g("league_home_boost") >= 7 and g("congestion") >= 6
    elif name == "BLUE_BLOOD_TRAP":
        return g("line_movement") >= 8 and g("off_ranking", 10) <= 5
    elif name == "MARCH_MADNESS_UPSET":
        if g("off_ranking") <= 3:
            return False
        return g("conference_strength") >= 7 and g("motivation") >= 8 and g("line_movement") >= 7
    elif name == "TEMPO_TRAP":
        if g("def_ranking") <= 3:
            return False
        return g("pace") >= 8 and g("tempo_real") >= 7 and g("off_ranking") >= 7
    elif name == "CONFERENCE_MISMATCH":
        if g("form") <= 3:
            return False
        return g("conference_strength") >= 8 and g("off_ranking") >= 7 and g("def_ranking") >= 7
    elif name == "HOME_COURT_CAULDRON":
        if g("star_player") <= 3:
            return False
        return g("home_away") >= 8 and g("form") >= 7 and g("motivation") >= 7
    elif name == "DEPTH_DRAIN":
        if g("form") >= 8:
            return False
        return g("depth", 10) <= 3 and g("pace") >= 7
    elif name == "TOURNAMENT_PEDIGREE":
        if g("conference_strength") <= 3:
            return False
        return g("tournament_exp") >= 8 and g("form") >= 6 and g("motivation") >= 7
    elif name == "THREE_POINT_STORM":
        if g("def_ranking", 10) <= 3:
            return False
        return g("three_pt_rate") >= 8 and g("off_ranking") >= 7 and g("pace") >= 7
    elif name == "B2B_CORPSE":
        if g("rest") >= 7:
            return False
        return g("b2b_fatigue") >= 8 and g("travel_distance") >= 7
    elif name == "ALTITUDE_BLEED":
        if g("form") >= 8:
            return False
        return g("altitude") >= 8 and g("travel_distance") >= 7 and g("b2b_fatigue") >= 6
    elif name == "PACE_MISMATCH":
        if g("def_ranking", 10) <= 3:
            return False
        return g("pace") >= 8 and g("off_ranking") >= 7 and g("quarter_pace") >= 7
    elif name == "LOAD_MANAGEMENT_ARB":
        if g("form", 10) <= 3:
            return False
        return g("star_player", 10) <= 4 and g("bench_diff") >= 7 and g("line_movement") >= 7
    elif name == "CLUTCH_LOCK":
        if g("star_player", 10) <= 4:
            return False
        return g("late_game_strength") >= 8 and g("def_ranking") >= 7 and g("form") >= 7
    elif name == "TURNOVER_PRESSURE":
        if g("off_ranking", 10) <= 4:
            return False
        return g("turnover_rate") >= 8 and g("def_ranking") >= 7
    elif name == "REF_PACE_BOOST":
        if g("def_ranking") >= 8:
            return False
        return g("referee_pace") >= 8 and g("pace") >= 7 and g("off_ranking") >= 7
    elif name == "WEATHER_FADE":
        if g("def_ranking") >= 8:
            return False
        return g("weather") <= 3 and g("home_away") <= 4 and g("form") <= 5
    elif name == "DOME_TEAM_FREEZE":
        if g("form") >= 8:
            return False
        return g("weather") <= 3 and g("home_away") <= 4 and g("pace") >= 7
    elif name == "DIVISIONAL_DOGFIGHT":
        if g("star_player") <= 3:
            return False
        return g("divisional") >= 7 and g("motivation") >= 7 and g("home_away") >= 6
    elif name == "TURNOVER_MACHINE":
        if g("off_ranking") <= 3:
            return False
        return g("turnover_diff") >= 8 and g("def_ranking") >= 7
    elif name == "RED_ZONE_HAMMER":
        if g("turnover_diff") <= 3:
            return False
        return g("red_zone") >= 8 and g("off_ranking") >= 7
    elif name == "PRIMETIME_LETDOWN":
        if g("star_player") >= 8:
            return False
        return g("motivation") <= 4 and g("form") <= 4 and g("home_away") <= 4
    elif name == "QB_WEATHER_EDGE":
        if g("off_ranking") <= 4:
            return False
        return g("weather") <= 4 and g("star_player") >= 8 and g("rest") >= 6
    elif name == "GROUND_AND_POUND":
        if g("off_ranking") <= 3:
            return False
        return g("pace") <= 4 and g("def_ranking") >= 7 and g("rest") >= 6
    elif name == "COACHING_MISMATCH":
        if g("star_player") <= 3:
            return False
        return g("coaching") >= 8 and g("motivation") >= 6
    elif name == "SCHEDULE_TRAP":
        if g("form") >= 8:
            return False
        return g("rest") <= 3 and g("home_away") <= 4 and g("motivation") <= 4
    elif name == "RECRUITING_GAP":
        if g("coaching_change") >= 7:
            return False
        return g("recruiting") >= 8 and g("off_ranking") >= 7
    elif name == "HOME_FORTRESS_CFB":
        if g("star_player") <= 3:
            return False
        return g("home_away") >= 8 and g("motivation") >= 7 and g("form") >= 6
    elif name == "COACHING_CHAOS":
        if g("recruiting") >= 8:
            return False
        return g("coaching_change") >= 8 and g("form", 10) <= 4
    elif name == "RIVALRY_UPSET":
        if g("off_ranking") <= 3:
            return False
        return g("h2h") >= 7 and g("motivation") >= 8 and g("home_away") >= 6
    elif name == "PORTAL_FLUX":
        if g("recruiting") >= 7:
            return False
        return g("depth", 10) <= 4 and g("coaching_change") >= 6
    # MMA chains
    elif name == "REACH_STRIKER":
        if g("ground_game") <= 3:
            return False
        return g("reach_advantage") >= 8 and g("off_ranking") >= 7
    elif name == "GRAPPLER_TRAP":
        if g("reach_advantage") <= 3:
            return False
        return g("ground_game") >= 8 and g("def_ranking") >= 7 and g("finish_rate") >= 6
    elif name == "CAMP_EDGE":
        if g("star_player") <= 3:
            return False
        return g("camp_quality") >= 8 and g("form") >= 7
    elif name == "FINISH_THREAT":
        if g("def_ranking") <= 3:
            return False
        return g("finish_rate") >= 8 and g("off_ranking") >= 7
    elif name == "RING_RUST":
        if g("camp_quality") >= 8:
            return False
        return g("rest") >= 8 and g("form", 10) <= 4
    # Boxing chains
    elif name == "REACH_KING":
        if g("form") <= 3:
            return False
        return g("reach_advantage") >= 8 and g("off_ranking") >= 7
    elif name == "SOUTHPAW_ANGLE":
        if g("reach_advantage") <= 3:
            return False
        return g("stance_matchup") >= 8 and g("form") >= 6
    elif name == "RING_RUST_BOX":
        if g("form") >= 7:
            return False
        return g("activity", 10) <= 3 and g("rest") >= 8
    elif name == "KO_ARTIST":
        if g("def_ranking") <= 3:
            return False
        return g("finish_rate") >= 8 and g("off_ranking") >= 8
    return False


# ─── NFL Scoring Functions ────────────────────────────────────────────────────

def score_weather(game: dict) -> tuple:
    wx = game.get("weather") or {}
    if not wx:
        return 5, "no weather data"
    condition = (wx.get("condition") or "").lower()
    if "dome" in condition:
        return 7, "Dome game"
    temp = wx.get("temp")
    wind_raw = wx.get("wind") or ""
    wind_mph = 0
    if isinstance(wind_raw, (int, float)):
        wind_mph = float(wind_raw)
    elif isinstance(wind_raw, str):
        parts = wind_raw.replace("mph", "").strip().split()
        for p in parts:
            try:
                wind_mph = float(p)
                break
            except ValueError:
                continue
    if temp is not None:
        try:
            temp = float(temp)
        except (TypeError, ValueError):
            temp = None
    if temp is not None and temp < 32 and wind_mph > 15:
        return 2, f"HARSH: {temp:.0f}F, wind {wind_mph:.0f}mph"
    if temp is not None and temp < 32:
        return 3, f"Cold: {temp:.0f}F, wind {wind_mph:.0f}mph"
    if wind_mph > 15:
        return 4, f"Windy: {wind_mph:.0f}mph, {temp or '?'}F"
    if temp is not None and temp >= 60:
        return 8, f"Warm/calm: {temp:.0f}F, wind {wind_mph:.0f}mph"
    return 6, f"Moderate: {temp or '?'}F, wind {wind_mph:.0f}mph"


def score_turnover_diff(profile: dict) -> tuple:
    td = profile.get("turnover_diff")
    if td is None:
        return 5, "no turnover data"
    if td >= 10:
        s = 9
    elif td >= 5:
        s = 7
    elif td >= 0:
        s = 5
    elif td >= -5:
        s = 3
    else:
        s = 2
    return _clamp(s), f"TO diff {td:+d}"


def score_red_zone(profile: dict) -> tuple:
    pct = profile.get("red_zone_pct")
    if pct is None:
        return 5, "no red zone data"
    if pct >= 65:
        s = 9
    elif pct >= 55:
        s = 7
    elif pct >= 50:
        s = 5
    else:
        s = 3
    return _clamp(s), f"RZ scoring {pct:.1f}%"


def score_divisional(game: dict, pick_side: str) -> tuple:
    return 5, "no divisional data"


def score_coaching(profile: dict) -> tuple:
    return 5, "no coaching data"


# ─── Soccer Scoring Functions ─────────────────────────────────────────────────

def score_goalkeeper(game: dict, pick_side: str) -> tuple:
    profile = game.get(f"{pick_side}_profile", {}) or {}
    keeper_name = profile.get("goalkeeper") or profile.get("keeper") or ""
    if not keeper_name:
        return 5, "no goalkeeper data"
    tier = _soccer_keeper_tier(keeper_name)
    tier_map = {"ELITE": 9, "GOOD": 7}
    score = tier_map.get(tier, 5)
    note = f"{keeper_name}: {tier or 'unknown'}"
    return _clamp(score), note


def score_xg_diff(profile: dict) -> tuple:
    return 5, "no xG data"


LEAGUE_HOME_BOOST_MAP = {
    "soccer_turkey_super_league": 8,
    "soccer_mexico_ligamx": 8,
    "soccer_brazil_campeonato": 8,
    "soccer_epl": 5,
    "soccer_england_league1": 5,
    "soccer_germany_bundesliga": 5,
    "soccer_germany_bundesliga2": 5,
    "soccer_usa_mls": 4,
    "soccer_spain_la_liga": 6,
    "soccer_italy_serie_a": 6,
    "soccer_france_ligue_one": 5,
}


def score_squad_rotation(game: dict, pick_side: str) -> tuple:
    profile = game.get(f"{pick_side}_profile", {}) or {}
    congestion = profile.get("matches_in_10d") or profile.get("congestion_10d")
    if congestion is None:
        return 5, "no congestion data for rotation"
    congestion = int(congestion)
    if congestion >= 3:
        return 8, f"HIGH rotation risk: {congestion} matches in 10d"
    elif congestion == 2:
        return 6, f"Moderate rotation: {congestion} matches in 10d"
    elif congestion <= 1:
        return 2, f"LOW rotation risk: {congestion} matches in 10d"
    return 5, f"{congestion} matches in 10d"


def score_league_home_boost(game: dict, pick_side: str) -> tuple:
    league = (game.get("odds_key") or game.get("league") or "").lower()
    boost = LEAGUE_HOME_BOOST_MAP.get(league)
    if boost is not None:
        is_home = (pick_side == "home")
        if is_home:
            return _clamp(boost), f"League home boost: {league} ({boost})"
        else:
            inv = 10 - boost
            return _clamp(inv), f"League home boost (away): {league} ({inv})"
    return 5, f"no league home boost for {league}"


def score_set_piece(profile: dict) -> tuple:
    return 5, "no set piece data"


# ─── NCAAB Scoring Functions ──────────────────────────────────────────────────

def score_conference_strength(profile: dict) -> tuple:
    return 5, "no conference data"


def score_tournament_exp(profile: dict) -> tuple:
    return 5, "no tournament data"


def score_tempo_real(profile: dict, opp: dict, sport: str) -> tuple:
    if profile.get("pace_L5"):
        return score_pace_matchup(profile, opp, sport)
    return 5, "no tempo data"


# ─── NCAAF Scoring Functions ──────────────────────────────────────────────────

def score_recruiting(profile: dict) -> tuple:
    return 5, "no recruiting data"


def score_coaching_change(profile: dict) -> tuple:
    return 5, "no coaching data"


# ─── MMA / Boxing Scoring Functions ───────────────────────────────────────────

def score_reach_advantage(game: dict, pick_side: str) -> tuple:
    home_f = game.get("home_fighter") or {}
    away_f = game.get("away_fighter") or {}
    fighter = home_f if pick_side == "home" else away_f
    opp = away_f if pick_side == "home" else home_f
    f_reach = fighter.get("reach_inches")
    o_reach = opp.get("reach_inches")
    if f_reach is None or o_reach is None:
        return 5, "no reach data"
    try:
        diff = float(f_reach) - float(o_reach)
    except (TypeError, ValueError):
        return 5, "no reach data"
    if diff >= 4:
        return 9, f"reach +{diff:.0f}in (big advantage)"
    elif diff >= 2:
        return 7, f"reach +{diff:.0f}in (advantage)"
    elif diff > -2:
        return 5, f"reach {diff:+.0f}in (neutral)"
    elif diff > -4:
        return 3, f"reach {diff:+.0f}in (disadvantage)"
    return 2, f"reach {diff:+.0f}in (big disadvantage)"


def score_finish_rate(game: dict, pick_side: str) -> tuple:
    home_f = game.get("home_fighter") or {}
    away_f = game.get("away_fighter") or {}
    fighter = home_f if pick_side == "home" else away_f
    if not fighter:
        return 5, "no fighter data"
    ko_pct = fighter.get("ko_pct")
    if ko_pct is None:
        return 5, "no KO% data"
    try:
        ko_pct = float(ko_pct)
    except (TypeError, ValueError):
        return 5, "no KO% data"
    if ko_pct >= 70:
        return 9, f"KO%: {ko_pct:.0f}% (elite finisher)"
    elif ko_pct >= 50:
        return 7, f"KO%: {ko_pct:.0f}% (good finisher)"
    elif ko_pct >= 30:
        return 5, f"KO%: {ko_pct:.0f}% (average)"
    return 3, f"KO%: {ko_pct:.0f}% (decision fighter)"


def score_ground_game(game: dict, pick_side: str) -> tuple:
    return 5, "no ground game data"


def score_camp_quality(game: dict, pick_side: str) -> tuple:
    return 5, "no camp data"


def score_stance_matchup(game: dict, pick_side: str) -> tuple:
    home_f = game.get("home_fighter") or {}
    away_f = game.get("away_fighter") or {}
    fighter = home_f if pick_side == "home" else away_f
    opp = away_f if pick_side == "home" else home_f
    stance = (fighter.get("stance") or "").lower()
    opp_stance = (opp.get("stance") or "").lower()
    if not stance or not opp_stance:
        return 5, "no stance data"
    if stance == "southpaw" and opp_stance == "orthodox":
        return 8, "Southpaw vs Orthodox (advantage)"
    if stance == "orthodox" and opp_stance == "southpaw":
        return 3, "Orthodox vs Southpaw (disadvantage)"
    return 5, f"{stance} vs {opp_stance} (neutral)"


def score_activity(game: dict, pick_side: str) -> tuple:
    return 5, "no activity data"


# ─── NEW-AGE Scorer Functions (layered on existing data) ──────────────────────

def score_scoring_margin_diff(game: dict, pick_side: str) -> tuple:
    """Goal/run differential: PPG minus OPP_PPG for both sides, compare."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {}) or {}
    ppg = profile.get("ppg_L5", 0) or 0
    opp_ppg = profile.get("opp_ppg_L5", 0) or 0
    o_ppg = opp.get("ppg_L5", 0) or 0
    o_opp = opp.get("opp_ppg_L5", 0) or 0
    if not ppg and not opp_ppg:
        return 5, "no scoring data"
    our_diff = ppg - opp_ppg
    their_diff = o_ppg - o_opp
    delta = our_diff - their_diff
    score = 5.0 + delta * 0.8
    return _clamp(score), f"margin diff {our_diff:+.1f} vs {their_diff:+.1f} (delta {delta:+.1f})"


def score_home_away_split(game: dict, pick_side: str) -> tuple:
    """How much better/worse is this team in their current venue context?"""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    is_home = pick_side == "home"
    split_rec = profile.get("home_record" if is_home else "away_record", "")
    if not split_rec or "-" not in split_rec:
        return 5, "no split data"
    parts = split_rec.replace("-", " ").split()
    try:
        wins = int(parts[0])
        losses = int(parts[1])
        total = wins + losses
        if total < 5:
            return 5, f"small sample ({split_rec})"
        pct = wins / total
        score = 5.0 + (pct - 0.5) * 8
        venue = "home" if is_home else "away"
        return _clamp(score), f"{venue} {split_rec} ({pct:.3f})"
    except (ValueError, IndexError):
        return 5, f"parse error: {split_rec}"


def score_goalie_tier_delta(game: dict, pick_side: str) -> tuple:
    """Difference in goalie tier between the two sides. ELITE vs AVERAGE = big edge."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {}) or {}
    our_g = (profile.get("starting_goalie") or {}).get("name", "TBD")
    opp_g = (opp.get("starting_goalie") or {}).get("name", "TBD")
    tier_map = {"ELITE": 3, "GOOD": 2, "AVERAGE": 1, "UNKNOWN": 0}
    def _tier(name):
        if not name or name == "TBD":
            return 0
        last = name.strip().lower().split()[-1]
        if last in _BATCH_ELITE_GOALIES:
            return 3
        if last in _BATCH_GOOD_GOALIES:
            return 2
        return 1
    ours = _tier(our_g)
    theirs = _tier(opp_g)
    delta = ours - theirs
    if delta >= 2:
        return 8.5, f"ELITE vs AVG ({our_g} vs {opp_g})"
    if delta == 1:
        return 6.5, f"tier edge ({our_g} vs {opp_g})"
    if delta == 0:
        return 5, f"even ({our_g} vs {opp_g})"
    if delta == -1:
        return 3.5, f"tier disadvantage ({our_g} vs {opp_g})"
    return 2, f"AVG vs ELITE ({our_g} vs {opp_g})"


def score_special_teams_combined(game: dict, pick_side: str) -> tuple:
    """Combined PP% + PK% edge. Teams elite on both = massive special teams edge."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {}) or {}
    # Reuse pp/pk scorer logic but combine
    pp = profile.get("pp_pct", profile.get("powerplay_pct"))
    pk = profile.get("pk_pct", profile.get("penalty_kill_pct"))
    if pp is None and pk is None:
        return 5, "no special teams data"
    # Simple: both above average = boost, both below = drop
    pp_score = 5.0
    pk_score = 5.0
    if pp is not None:
        try:
            pp = float(pp)
            pp_score = 5.0 + (pp - 20.0) * 0.3  # 20% is average
        except (ValueError, TypeError):
            pass
    if pk is not None:
        try:
            pk = float(pk)
            pk_score = 5.0 + (pk - 80.0) * 0.3  # 80% is average
        except (ValueError, TypeError):
            pass
    combined = (pp_score + pk_score) / 2
    return _clamp(combined), f"PP+PK combined {combined:.1f}"


def score_schedule_density(game: dict, pick_side: str) -> tuple:
    """Games in last 10 days — schedule grind factor."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {}) or {}
    our_games = profile.get("matches_in_10d", 0) or 0
    their_games = opp.get("matches_in_10d", 0) or 0
    if not our_games and not their_games:
        return 5, "no schedule data"
    delta = their_games - our_games  # positive = opponent is more fatigued
    score = 5.0 + delta * 0.8
    return _clamp(score), f"schedule {our_games} vs {their_games} games in 10d"


def score_league_position_gap(game: dict, pick_side: str) -> tuple:
    """Standing position gap — #1 vs #20 is a mismatch."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {}) or {}
    our_pos = profile.get("league_position")
    their_pos = opp.get("league_position")
    if our_pos is None or their_pos is None:
        return 5, "no standing data"
    try:
        our_pos = int(our_pos)
        their_pos = int(their_pos)
    except (ValueError, TypeError):
        return 5, "parse error"
    gap = their_pos - our_pos  # positive = we're higher in standings
    score = 5.0 + gap * 0.25
    return _clamp(score), f"standing #{our_pos} vs #{their_pos} (gap {gap:+d})"


def score_bullpen_k_dominance(game: dict, pick_side: str) -> tuple:
    """Bullpen strikeout dominance — K-rate pen vs contact pen."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {}) or {}
    # Use bullpen ERA as proxy — lower ERA correlates with higher K rate
    bp = profile.get("bullpen") or {}
    opp_bp = opp.get("bullpen") or {}
    era = bp.get("bullpen_era_L7")
    opp_era = opp_bp.get("bullpen_era_L7")
    if era is None and opp_era is None:
        return 5, "no bullpen K data"
    try:
        our_era = float(era) if era is not None else 4.0
        their_era = float(opp_era) if opp_era is not None else 4.0
    except (ValueError, TypeError):
        return 5, "parse error"
    # Lower ERA = better. Each 0.5 ERA difference = ~1 point
    delta = their_era - our_era  # positive = our pen is better
    score = 5.0 + delta * 1.2
    return _clamp(score), f"pen ERA {our_era:.2f} vs {their_era:.2f} (delta {delta:+.1f})"


def score_k_rate_vs_barrel(game: dict, pick_side: str) -> tuple:
    """THE matchup: our pitching staff K rate vs their lineup power.
    K pitchers vs HR-or-nothing hitters = strikeouts. Peter's thesis."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {}) or {}
    sp = profile.get("starting_pitcher") or {}
    opp_splits = opp.get("lineup_vs_hand") or {}
    k9 = sp.get("k9")
    opp_ops = opp_splits.get("ops_vs_hand")
    opp_hr = opp_splits.get("hr_vs_hand")
    opp_avg = opp_splits.get("avg_vs_hand")
    if k9 is None or opp_ops is None:
        return 5, "no K vs barrel data"
    try:
        k9f = float(k9)
        ops_f = float(opp_ops)
        avg_f = float(opp_avg) if opp_avg is not None else 0.260
        hr_i = int(opp_hr) if opp_hr is not None else 10
    except (ValueError, TypeError):
        return 5, "parse error"
    # High K pitcher (9+) vs power lineup (high OPS, high HR, low AVG) = edge
    is_k_pitcher = k9f >= 9.0
    is_power_lineup = ops_f >= 0.750 and avg_f <= 0.250  # swing big, miss big
    score = 5.0
    if is_k_pitcher and is_power_lineup:
        score = 8.0  # K pitcher vs HR-or-bust = Ks
    elif is_k_pitcher:
        score = 6.5  # K pitcher vs any lineup = lean
    elif not is_k_pitcher and is_power_lineup:
        score = 3.5  # contact pitcher vs power lineup = danger
    # K/9 gradient
    score += (k9f - 8.5) * 0.5
    # Power lineup penalty
    if ops_f >= 0.800:
        score -= 0.5
    return _clamp(score), f"K9 {k9f:.1f} vs OPS {ops_f:.3f}/AVG {avg_f:.3f}/HR {hr_i}"


def score_run_differential_l5(game: dict, pick_side: str) -> tuple:
    """Run/goal differential over L5 — margin matters more than record."""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    margin = profile.get("margin_L5", profile.get("L5_margin", 0))
    if margin is None:
        return 5, "no margin data"
    try:
        margin = float(margin)
    except (ValueError, TypeError):
        return 5, "parse error"
    score = 5.0 + margin * 0.6
    return _clamp(score), f"L5 margin {margin:+.1f}"


def score_record_strength(game: dict, pick_side: str) -> tuple:
    """Overall record win% — are they actually a good team?"""
    profile = game.get(f"{pick_side}_profile", {}) or {}
    rec = profile.get("record", "")
    if not rec or "-" not in rec:
        return 5, "no record"
    parts = rec.replace("-", " ").split()
    try:
        wins = int(parts[0])
        losses = int(parts[1])
        total = wins + losses
        if total < 10:
            return 5, f"small sample ({rec})"
        pct = wins / total
        score = 5.0 + (pct - 0.5) * 10
        return _clamp(score), f"record {rec} ({pct:.3f})"
    except (ValueError, IndexError):
        return 5, f"parse error: {rec}"


# ─── Variable Config Per Sport ─────────────────────────────────────────────────

SPORT_VARIABLES = {
    "NBA": {
        "star_player": 9, "rest": 9, "off_ranking": 8, "def_ranking": 8,
        "pace": 7, "form": 7, "road_trip": 7, "h2h": 6, "ats": 6,
        "line_movement": 5, "home_away": 5, "depth": 4, "motivation": 5,
        "late_game_strength": 7, "quarter_pace": 6, "bench_diff": 6,
        "three_pt_rate": 8, "b2b_fatigue": 8, "travel_distance": 6,
        "altitude": 7, "referee_pace": 5, "turnover_rate": 6,
    },
    "NHL": {
        # Tier 1: Goalie is king (consensus: 77% models cite goalie metrics)
        "goalie": 10.8, "goalie_workload": 9.7, "goalie_tier_delta": 9.2,
        # Tier 2: Team strength + possession (58% cite xG/Corsi)
        "off_ranking": 8.9, "def_ranking": 8.6, "scoring_margin_diff": 8.3,
        "star_player": 8.1,
        # Tier 3: Special teams + situational
        "pp_pct": 7.9, "pk_pct": 7.5, "special_teams_combined": 7.3,
        "rest": 7.7, "b2b_flag": 7.1, "form": 6.9,
        # Tier 4: Matchup + context
        "home_away_split": 6.7, "road_trip": 6.5, "travel_fatigue": 6.3,
        "h2h": 6.1, "depth": 5.9, "schedule_density": 5.7,
        "shot_quality": 5.5, "altitude": 5.3,
        # Tier 5: Market + situational
        "ats": 5.1, "line_movement": 4.9, "motivation": 4.7,
        "league_position_gap": 4.5, "record_strength": 4.3,
        "run_differential_l5": 4.1, "home_away": 3.9,
    },
    "MLB": {
        # Tier 1: Bullpen is king + K matchup thesis (Peter's philosophy)
        "bullpen": 10.9, "bullpen_k_dominance": 10.4, "k_rate_vs_barrel": 9.8,
        "bullpen_fatigue": 9.5,
        # Tier 2: Lineup quality + starter depth (NOT starter name)
        "lineup_vs_hand": 9.2, "starter_depth": 8.9, "lineup_dna": 8.6,
        "pitcher_hitter_archetype": 8.3,
        # Tier 3: Offensive/defensive strength
        "off_ranking": 8.1, "def_ranking": 7.9, "scoring_margin_diff": 7.7,
        "plate_discipline": 7.5, "star_player": 7.3,
        # Tier 4: Pitcher detail + matchup depth
        "pitcher_profile": 7.1, "starting_pitcher": 6.9, "bullpen_sequencing": 6.7,
        "platoon_depth": 6.5, "pitcher_fatigue": 6.3,
        # Tier 5: Context + environment
        "park_factor": 6.1, "weather_factor": 5.9, "umpire": 5.7,
        "gb_fb_ratio": 5.5, "form": 5.3, "run_environment": 5.1,
        # Tier 6: Situational + market
        "home_away_split": 4.9, "rest": 4.7, "h2h": 4.5,
        "run_differential_l5": 4.3, "record_strength": 4.1,
        "ats": 3.9, "line_movement": 3.7, "home_away": 3.5,
        "depth": 3.3, "motivation": 3.1, "manager_tendencies": 2.9,
        "schedule_density": 2.7,
    },
    "SOCCER": {
        "congestion": 6, "form": 8, "star_player": 8, "off_ranking": 9,
        "def_ranking": 9, "home_away": 7, "rest": 4, "h2h": 6,
        "motivation": 6, "ats": 6, "line_movement": 6, "depth": 4,
        "goalkeeper": 8, "squad_rotation": 6,
        "league_home_boost": 5,
    },
    "NCAAB": {
        "off_ranking": 9, "def_ranking": 9, "star_player": 9, "line_movement": 9,
        "pace": 8, "ats": 8, "conference_strength": 8, "form": 7, "tempo_real": 7,
        "h2h": 6, "home_away": 6, "depth": 7, "motivation": 6, "tournament_exp": 6,
        "rest": 5,
    },
    "NFL": {
        "off_ranking": 9, "def_ranking": 9, "star_player": 8, "form": 8,
        "home_away": 7, "rest": 7, "pace": 7, "weather": 7, "turnover_diff": 7,
        "h2h": 6, "ats": 7, "red_zone": 6, "divisional": 6,
        "line_movement": 6, "motivation": 6, "depth": 5, "coaching": 5,
    },
    "NCAAF": {
        "off_ranking": 9, "def_ranking": 9, "star_player": 8, "form": 8,
        "home_away": 8, "rest": 6, "h2h": 5, "ats": 7,
        "line_movement": 7, "motivation": 7, "depth": 5, "pace": 7,
        "recruiting": 7, "coaching_change": 6,
    },
    "MMA": {
        "form": 9, "reach_advantage": 8, "star_player": 7,
        "motivation": 7, "finish_rate": 7, "rest": 5, "h2h": 5,
        "line_movement": 5,
    },
    "BOXING": {
        "form": 9, "reach_advantage": 8, "star_player": 7,
        "motivation": 7, "stance_matchup": 6, "finish_rate": 6,
        "rest": 5, "h2h": 5, "line_movement": 5,
    },
    "WNBA": {
        "off_ranking": 9, "def_ranking": 9, "star_player": 10, "form": 8,
        "line_movement": 7, "h2h": 6, "ats": 7, "home_away": 4,
        "rest": 5, "depth": 8, "motivation": 6, "three_pt_rate": 5,
        "b2b_fatigue": 4, "travel_distance": 7, "altitude": 3,
        "bench_diff": 7, "turnover_rate": 6,
    },
    "TENNIS": {
        "surface_edge": 10, "form": 9, "h2h": 8, "serve_dominance": 9,
        "return_game": 8, "ranking_gap": 7, "fatigue": 8,
        "mental_clutch": 7, "star_player": 6, "weather_factor": 5,
        "home_away": 3, "line_movement": 6, "ats": 5, "motivation": 7,
    },
    "COLLEGE_BASEBALL": {
        "starting_pitcher": 10, "bullpen": 6, "off_ranking": 8, "def_ranking": 7,
        "form": 8, "home_away": 7, "weather_factor": 7, "h2h": 5, "ats": 5,
        "conference_strength": 7, "ranking_gap": 6, "rest": 5,
        "line_movement": 5, "motivation": 6, "star_player": 7, "depth": 4,
    },
}


# ─── Main Grade Function ──────────────────────────────────────────────────────

def grade_game(game: dict, pick_side: str) -> dict:
    """
    Grade a game for one side. Returns full breakdown.
    game dict needs: sport, home_profile, away_profile, odds, injuries, shifts
    """
    sport = game.get("sport", "NBA").upper()
    profile = game.get(f"{pick_side}_profile", {})
    opp_side = "away" if pick_side == "home" else "home"
    opp = game.get(f"{opp_side}_profile", {})

    var_weights = dict(SPORT_VARIABLES.get(sport, SPORT_VARIABLES["NBA"]))
    # Dynamic weight learning — override hardcoded weights when enough game data exists
    try:
        from dynamic_weights import get_adjusted_weights
        learned = get_adjusted_weights(sport)
        if learned:
            var_weights.update(learned)
    except Exception:
        pass  # Fall back to hardcoded weights silently
    variables = {}

    # Data availability checks — skip variables we have NO data for
    has_injuries = bool(game.get("injuries", {}).get("home") or game.get("injuries", {}).get("away"))
    has_rest = profile.get("rest_days") is not None
    has_form = bool(profile.get("L5"))
    has_h2h = profile.get("h2h_season", "0-0") != "0-0"
    has_shifts = bool(game.get("shifts", {}).get("spread_delta"))
    has_pace = bool(profile.get("pace_L5"))

    for var_name, weight in var_weights.items():
        available = True  # default: include in composite

        if var_name == "star_player":
            if has_injuries:
                if sport == "SOCCER":
                    score, note = score_soccer_key_player(game, pick_side)
                else:
                    score, note = score_star_player(game, pick_side)
            else:
                score, note = 5, "No injury data"
                available = False
        elif var_name == "rest":
            if has_rest:
                score, note = score_rest_advantage(profile, opp)
            else:
                score, note = 5, "No rest data"
                available = False
        elif var_name == "off_ranking":
            score, note = score_off_ranking(profile, opp, sport)
            if score == 5 and "No" in note:
                available = False
            # NHL: record-laundered ppg is not a real offense signal —
            # standings points diverge sharply from goal differential.
            if sport in ("NHL", "SOCCER") and profile.get("ppg_synthetic"):
                available = False
                note = f"{note} (synthetic from record)"
        elif var_name == "def_ranking":
            score, note = score_def_ranking(profile, opp, sport)
            if score == 5 and "No" in note:
                available = False
            if sport in ("NHL", "SOCCER") and profile.get("ppg_synthetic"):
                available = False
                note = f"{note} (synthetic from record)"
        elif var_name == "form":
            if has_form:
                score, note = score_recent_form(profile, opp)
            else:
                score, note = 5, "No L5 data"
                available = False
        elif var_name == "home_away":
            score, note = score_home_away(game, pick_side)
            if "?" in note:
                available = False
        elif var_name == "h2h":
            if has_h2h:
                score, note = score_h2h(profile)
            else:
                score, note = 5, "No H2H data"
                available = False
        elif var_name == "ats":
            score, note = score_ats_trend(profile)
            if profile.get("avg_margin_L10") is None:
                available = False
        elif var_name == "line_movement":
            if has_shifts:
                score, note = score_line_movement(game)
            else:
                score, note = 5, "No line movement data"
                available = False
        elif var_name == "road_trip":
            score, note = score_road_trip(profile)
            if note == "Neutral" and "road_trip_len" not in profile and "home_stand_len" not in profile:
                available = False
        elif var_name == "depth":
            if has_injuries:
                score, note = score_depth_injuries(game, pick_side)
            else:
                score, note = 5, "No injury data"
                available = False
        elif var_name == "pace":
            if has_pace:
                score, note = score_pace_matchup(profile, opp, sport)
            else:
                score, note = 5, "No pace data"
                available = False
        elif var_name == "motivation":
            score, note = score_motivation(game, pick_side)
        elif var_name == "starting_pitcher":
            score, note = score_starting_pitcher(game, pick_side)
            if note.startswith(_SP_PROXY_NOTE_PREFIX):
                available = False
        elif var_name == "starter_depth":
            score, note = score_starter_depth(game, pick_side)
            if "no " in note.lower():
                available = False
        elif var_name == "goalie":
            score, note = score_starting_goalie(game, pick_side)
            if note == "No goalie data":
                available = False
        elif var_name == "congestion":
            score, note = score_fixture_congestion(game, pick_side)
        elif var_name == "park_factor":
            score, note = score_park_factor(game, pick_side)
            if "unknown park" in note:
                available = False
        elif var_name == "bullpen":
            score, note = score_bullpen(game, pick_side)
            if note == "no bullpen data":
                available = False
        elif var_name == "lineup_vs_hand":
            score, note = score_lineup_vs_hand(game, pick_side)
            if note == "no lineup vs hand splits":
                available = False
        elif var_name == "pitcher_hitter_archetype":
            score, note = score_pitcher_hitter_archetype(game, pick_side)
            if "no pitcher-vs-lineup archetype data" in note:
                available = False
        elif var_name == "umpire":
            score, note = score_umpire(game, pick_side)
            if note == "no umpire data" or "unknown tendency" in note:
                available = False
        elif var_name == "late_game_strength":
            score, note = score_late_game_strength(game, pick_side)
            if note == "no quarter data":
                available = False
        elif var_name == "quarter_pace":
            score, note = score_quarter_pace(game, pick_side)
            if note == "no quarter data":
                available = False
        elif var_name == "bench_diff":
            score, note = score_bench_diff(game, pick_side)
            if note == "no bench data":
                available = False
        elif var_name == "pp_pct":
            score, note = score_pp_pct(profile)
            if note == "no PP data":
                available = False
        elif var_name == "pk_pct":
            score, note = score_pk_pct(profile)
            if note == "no PK data":
                available = False
        elif var_name == "goalie_workload":
            score, note = score_goalie_workload(game, pick_side)
            if note == "No goalie workload data":
                available = False
        elif var_name == "b2b_flag":
            score, note = score_b2b_flag(profile)
            if note == "No rest data":
                available = False
        elif var_name == "shot_quality":
            score, note = score_shot_quality(profile, opp)
            if note == "No shot quality data":
                available = False
        elif var_name == "travel_fatigue":
            score, note = score_travel_fatigue(profile, game, pick_side)
        elif var_name == "three_pt_rate":
            score, note = score_three_pt_rate(profile, opp)
            if note == "no PPG data":
                available = False
        elif var_name == "b2b_fatigue":
            score, note = score_b2b_fatigue(profile, opp)
            if note == "no rest data":
                available = False
        elif var_name == "travel_distance":
            score, note = score_travel_distance(profile, game, pick_side)
        elif var_name == "altitude":
            score, note = score_altitude(game, pick_side)
        elif var_name == "referee_pace":
            score, note = score_referee_pace(game)
            available = False
        elif var_name == "turnover_rate":
            score, note = score_turnover_rate(profile, opp)
            if note == "no defensive data":
                available = False
        elif var_name == "lineup_dna":
            score, note = score_lineup_dna(game, pick_side)
            if note == "no lineup DNA data":
                available = False
        elif var_name == "pitcher_profile":
            score, note = score_pitcher_profile(game, pick_side)
            if "no pitcher profile data" in note:
                available = False
        elif var_name == "bullpen_fatigue":
            score, note = score_bullpen_fatigue(game, pick_side)
            if note == "no bullpen fatigue data":
                available = False
        elif var_name == "weather_factor":
            score, note = score_weather_factor(game, pick_side)
            if note == "no weather data":
                available = False
        elif var_name == "gb_fb_ratio":
            score, note = score_gb_fb_ratio(game, pick_side)
            if note == "no GB/FB data":
                available = False
        elif var_name == "plate_discipline":
            score, note = score_plate_discipline(game, pick_side)
            if note == "no plate discipline data":
                available = False
        # ── MLB matchup depth variables ──
        elif var_name in ("bullpen_sequencing", "manager_tendencies", "platoon_depth", "pitcher_fatigue", "run_environment"):
            try:
                from services.mlb_matchup_depth import (
                    score_bullpen_sequencing, score_manager_tendencies,
                    score_platoon_depth, score_pitcher_fatigue, score_run_environment,
                )
                home_data = game.get("home_profile", {})
                away_data = game.get("away_profile", {})
                _depth_funcs = {
                    "bullpen_sequencing": lambda: score_bullpen_sequencing(home_data, away_data),
                    "manager_tendencies": lambda: score_manager_tendencies(home_data, away_data),
                    "platoon_depth": lambda: score_platoon_depth(home_data, away_data),
                    "pitcher_fatigue": lambda: score_pitcher_fatigue(home_data, away_data),
                    "run_environment": lambda: score_run_environment(home_data, away_data, game.get("park_factor")),
                }
                result = _depth_funcs[var_name]()
                side_result = result.get(pick_side)
                if side_result and side_result[0] is not None:
                    score, note = side_result
                else:
                    score, note = 5, "data unavailable"
                    available = False
            except Exception:
                score, note = 5, "matchup depth module error"
                available = False
        # ── NFL new variables ──
        elif var_name == "weather":
            wx = game.get("weather") or {}
            if wx:
                score, note = score_weather(game)
            else:
                score, note = 5, "no weather data"
                available = False
        elif var_name == "turnover_diff":
            score, note = score_turnover_diff(profile)
            if profile.get("turnover_diff") is None:
                available = False
        elif var_name == "red_zone":
            score, note = score_red_zone(profile)
            if profile.get("red_zone_pct") is None:
                available = False
        elif var_name == "divisional":
            score, note = score_divisional(game, pick_side)
            available = False
        elif var_name == "coaching":
            score, note = score_coaching(profile)
            available = False
        # ── Soccer new variables ──
        elif var_name == "goalkeeper":
            score, note = score_goalkeeper(game, pick_side)
            if "no goalkeeper data" in note:
                available = False
        elif var_name == "xg_diff":
            score, note = score_xg_diff(profile)
            available = False
        elif var_name == "squad_rotation":
            score, note = score_squad_rotation(game, pick_side)
            if "no congestion data" in note:
                available = False
        elif var_name == "league_home_boost":
            score, note = score_league_home_boost(game, pick_side)
            if "no league home boost" in note:
                available = False
        elif var_name == "set_piece":
            score, note = score_set_piece(profile)
            available = False
        # ── NCAAB new variables ──
        elif var_name == "conference_strength":
            score, note = score_conference_strength(profile)
            available = False
        elif var_name == "tournament_exp":
            score, note = score_tournament_exp(profile)
            available = False
        elif var_name == "tempo_real":
            score, note = score_tempo_real(profile, opp, sport)
            if note == "no tempo data":
                available = False
        # ── NCAAF new variables ──
        elif var_name == "recruiting":
            score, note = score_recruiting(profile)
            available = False
        elif var_name == "coaching_change":
            score, note = score_coaching_change(profile)
            available = False
        # ── MMA / Boxing new variables ──
        elif var_name == "reach_advantage":
            score, note = score_reach_advantage(game, pick_side)
            if note == "no reach data":
                available = False
        elif var_name == "finish_rate":
            score, note = score_finish_rate(game, pick_side)
            if "no fighter data" in note or "no KO% data" in note:
                available = False
        elif var_name == "ground_game":
            score, note = score_ground_game(game, pick_side)
            available = False
        elif var_name == "camp_quality":
            score, note = score_camp_quality(game, pick_side)
            available = False
        elif var_name == "stance_matchup":
            score, note = score_stance_matchup(game, pick_side)
            if note == "no stance data":
                available = False
        elif var_name == "activity":
            score, note = score_activity(game, pick_side)
            available = False
        # ── New-age variables (layered on existing data) ──
        elif var_name == "scoring_margin_diff":
            score, note = score_scoring_margin_diff(game, pick_side)
            if "no scoring" in note:
                available = False
        elif var_name == "home_away_split":
            score, note = score_home_away_split(game, pick_side)
            if "no split" in note or "small sample" in note:
                available = False
        elif var_name == "goalie_tier_delta":
            score, note = score_goalie_tier_delta(game, pick_side)
            if "TBD" in note and "TBD" in note[note.find("vs"):]:
                available = False
        elif var_name == "special_teams_combined":
            score, note = score_special_teams_combined(game, pick_side)
            if "no special" in note:
                available = False
        elif var_name == "schedule_density":
            score, note = score_schedule_density(game, pick_side)
            if "no schedule" in note:
                available = False
        elif var_name == "league_position_gap":
            score, note = score_league_position_gap(game, pick_side)
            if "no standing" in note:
                available = False
        elif var_name == "bullpen_k_dominance":
            score, note = score_bullpen_k_dominance(game, pick_side)
            if "no bullpen K" in note:
                available = False
        elif var_name == "k_rate_vs_barrel":
            score, note = score_k_rate_vs_barrel(game, pick_side)
            if "no K vs barrel" in note:
                available = False
        elif var_name == "run_differential_l5":
            score, note = score_run_differential_l5(game, pick_side)
            if "no margin" in note:
                available = False
        elif var_name == "record_strength":
            score, note = score_record_strength(game, pick_side)
            if "no record" in note or "small sample" in note:
                available = False
        else:
            score, note = 5, f"{var_name}: no data"
            available = False

        variables[var_name] = {
            "score": _clamp(score),
            "weight": weight,
            "weighted": round(_clamp(score) * weight, 1),
            "note": note,
            "available": available,
        }

    # Composite — only from AVAILABLE variables (skip those with no data)
    active = {k: v for k, v in variables.items() if v.get("available", True)}
    total_weighted = sum(v["weighted"] for v in active.values())
    max_possible = sum(v["weight"] * 10 for v in active.values())
    composite = round(total_weighted / max_possible * 10, 2) if max_possible > 0 else 5.0
    composite = _apply_spread_amplifier(composite, variables)

    # Chains
    v_scores = {k: var["score"] for k, var in variables.items()}

    # Data gate: require minimum real variables before chains can fire
    available_count = sum(1 for v in variables.values() if v.get("available", True))
    total_count = len(variables)
    data_coverage = available_count / total_count if total_count > 0 else 0
    chains_blocked = data_coverage < 0.5

    chains_fired = []
    chain_bonus = 0.0
    if not chains_blocked:
        for chain_name, cfg in CHAINS.items():
            if cfg["sports"] and sport not in cfg["sports"]:
                continue
            if check_chain(chain_name, v_scores):
                chain_bonus += cfg["bonus"]
                chains_fired.append(chain_name)

    chain_bonus = max(-CHAIN_CAP, min(chain_bonus, CHAIN_CAP))
    final = round(max(1.0, min(10.0, composite + chain_bonus)), 2)
    grade = score_to_grade(final)

    return {
        "grade": grade,
        "score": final,
        "composite": composite,
        "chain_bonus": chain_bonus,
        "chains_fired": chains_fired,
        "sizing": score_to_sizing(final),
        "confidence": min(95, max(40, int(55 + (final - 5) * 8))),
        "variables": variables,
        "pick_side": pick_side,
    }


def grade_game_total(game: dict) -> dict:
    """Grade over/under for a game. Returns verdict, score, confidence, factors."""
    sport = game.get("sport", "NBA").upper()
    home = game.get("home_profile", {}) or {}
    away = game.get("away_profile", {}) or {}
    odds = game.get("odds", {}) or {}
    total_line = odds.get("total", 0)

    if not total_line or total_line <= 0:
        return {"verdict": "SKIP", "score": 0, "confidence": 0, "factors": ["no total line"]}

    lean = 0.0
    factors = []

    # --- Universal signals ---

    # Offensive strength (both teams)
    home_ppg = home.get("ppg_L5", 0) or 0
    away_ppg = away.get("ppg_L5", 0) or 0
    home_opp_ppg = home.get("opp_ppg_L5", 0) or 0
    away_opp_ppg = away.get("opp_ppg_L5", 0) or 0

    if home_ppg and away_ppg:
        avg_ppg = (home_ppg + away_ppg) / 2
        scoring_avg = {
            "NBA": 114, "WNBA": 80, "NCAAB": 72, "NHL": 3.2, "MLB": 4.5,
            "NFL": 22, "NCAAF": 27, "SOCCER": 1.4,
        }
        avg = scoring_avg.get(sport, 114)
        if avg > 0:
            off_ratio = avg_ppg / avg
            if off_ratio >= 1.08:
                lean += 1.2
                factors.append(f"Both offenses hot (avg PPG {avg_ppg:.1f})")
            elif off_ratio >= 1.03:
                lean += 0.6
                factors.append(f"Above-avg offenses (avg PPG {avg_ppg:.1f})")
            elif off_ratio <= 0.92:
                lean -= 1.0
                factors.append(f"Both offenses cold (avg PPG {avg_ppg:.1f})")
            elif off_ratio <= 0.97:
                lean -= 0.4
                factors.append(f"Below-avg offenses (avg PPG {avg_ppg:.1f})")

    # Defensive strength (both teams)
    if home_opp_ppg and away_opp_ppg:
        avg_def = (home_opp_ppg + away_opp_ppg) / 2
        def_avg = {
            "NBA": 114, "WNBA": 80, "NCAAB": 72, "NHL": 3.2, "MLB": 4.5,
            "NFL": 22, "NCAAF": 27, "SOCCER": 1.4,
        }
        d_avg = def_avg.get(sport, 114)
        if d_avg > 0:
            def_ratio = avg_def / d_avg
            if def_ratio >= 1.08:
                lean += 1.0
                factors.append(f"Both defenses porous (avg allow {avg_def:.1f})")
            elif def_ratio >= 1.03:
                lean += 0.5
                factors.append(f"Below-avg defenses (avg allow {avg_def:.1f})")
            elif def_ratio <= 0.92:
                lean -= 1.2
                factors.append(f"Both defenses elite (avg allow {avg_def:.1f})")
            elif def_ratio <= 0.97:
                lean -= 0.5
                factors.append(f"Above-avg defenses (avg allow {avg_def:.1f})")

    # Pace/tempo
    home_pace = home.get("pace_L5", 0) or 0
    away_pace = away.get("pace_L5", 0) or 0
    if home_pace and away_pace:
        avg_pace = (home_pace + away_pace) / 2
        pace_avg = {
            "NBA": 225, "NCAAB": 70, "NHL": 60, "NFL": 63, "NCAAF": 63,
        }
        p_avg = pace_avg.get(sport, 0)
        if p_avg > 0:
            pace_ratio = avg_pace / p_avg
            if pace_ratio >= 1.06:
                lean += 0.8
                factors.append(f"Fast-paced matchup (avg pace {avg_pace:.1f})")
            elif pace_ratio >= 1.02:
                lean += 0.3
                factors.append(f"Above-avg pace ({avg_pace:.1f})")
            elif pace_ratio <= 0.94:
                lean -= 0.8
                factors.append(f"Slow grind matchup (avg pace {avg_pace:.1f})")
            elif pace_ratio <= 0.98:
                lean -= 0.3
                factors.append(f"Below-avg pace ({avg_pace:.1f})")

    # Recent form / scoring trend
    home_l5 = home.get("L5", "")
    away_l5 = away.get("L5", "")
    if home_l5 and away_l5:
        hw, hl = _parse_record(home_l5)
        aw, al = _parse_record(away_l5)
        total_wins = hw + aw
        total_games = hw + hl + aw + al
        if total_games >= 6:
            win_rate = total_wins / total_games
            if win_rate >= 0.7:
                lean += 0.4
                factors.append(f"Both teams in form (combined {total_wins}W in L5)")
            elif win_rate <= 0.3:
                lean -= 0.3
                factors.append(f"Both teams struggling ({total_wins}W in L5)")

    # Rest advantage — well-rested teams score more
    home_rest = home.get("rest_days")
    away_rest = away.get("rest_days")
    home_b2b = home.get("is_b2b", False)
    away_b2b = away.get("is_b2b", False)
    if home_rest is not None and away_rest is not None:
        if home_rest >= 3 and away_rest >= 3:
            lean += 0.3
            factors.append("Both teams well-rested")
        elif home_b2b and away_b2b:
            lean -= 0.3
            factors.append("Both on B2B — fatigue depresses scoring")
        elif home_b2b or away_b2b:
            pass  # wash — one rested, one tired

    # Total line movement
    shifts = game.get("shifts", {}) or {}
    total_open = shifts.get("total_open")
    if total_open and total_line:
        try:
            t_delta = float(total_line) - float(total_open)
            if t_delta >= 2.0:
                lean += 0.5
                factors.append(f"Total moved UP {t_delta:+.1f} (public on OVER)")
            elif t_delta >= 1.0:
                lean += 0.25
                factors.append(f"Total ticked up {t_delta:+.1f}")
            elif t_delta <= -2.0:
                lean -= 0.5
                factors.append(f"Total moved DOWN {t_delta:+.1f} (sharp UNDER)")
            elif t_delta <= -1.0:
                lean -= 0.25
                factors.append(f"Total ticked down {t_delta:+.1f}")
        except (ValueError, TypeError):
            pass

    # --- Sport-specific signals ---

    if sport == "MLB":
        # Starting pitcher quality
        home_sp = home.get("starting_pitcher", {}) or {}
        away_sp = away.get("starting_pitcher", {}) or {}
        home_era = home_sp.get("era") or home_sp.get("ERA")
        away_era = away_sp.get("era") or away_sp.get("ERA")
        home_tier = _pitcher_tier_from_stats(home_sp)
        away_tier = _pitcher_tier_from_stats(away_sp)

        tier_lean = {"ace": -1.2, "good": -0.6, "mid": 0, "bad": 0.7, "unknown": 0}
        sp_lean = tier_lean.get(home_tier, 0) + tier_lean.get(away_tier, 0)
        if abs(sp_lean) >= 0.5:
            lean += sp_lean
            factors.append(f"SP matchup: {home_tier} vs {away_tier} (lean {sp_lean:+.1f})")

        if home_era and away_era:
            try:
                avg_era = (float(home_era) + float(away_era)) / 2
                if avg_era >= 5.0:
                    lean += 0.6
                    factors.append(f"High avg SP ERA ({avg_era:.2f})")
                elif avg_era <= 2.75:
                    lean -= 0.6
                    factors.append(f"Low avg SP ERA ({avg_era:.2f})")
            except (ValueError, TypeError):
                pass

        # Bullpen fatigue
        home_bp = home.get("bullpen", {}) or {}
        away_bp = away.get("bullpen", {}) or {}
        home_tired = home_bp.get("bullpen_tired_arms", 0)
        away_tired = away_bp.get("bullpen_tired_arms", 0)
        total_tired = home_tired + away_tired
        if total_tired >= 5:
            lean += 0.8
            factors.append(f"Both bullpens fatigued ({total_tired} tired arms)")
        elif total_tired >= 3:
            lean += 0.4
            factors.append(f"Some bullpen fatigue ({total_tired} tired arms)")

        home_bp_era = home_bp.get("bullpen_era_L7", 4.0)
        away_bp_era = away_bp.get("bullpen_era_L7", 4.0)
        if home_bp_era and away_bp_era:
            avg_bp_era = (home_bp_era + away_bp_era) / 2
            if avg_bp_era >= 5.0:
                lean += 0.5
                factors.append(f"Bullpens struggling (avg ERA L7 {avg_bp_era:.2f})")
            elif avg_bp_era <= 3.0:
                lean -= 0.4
                factors.append(f"Bullpens locked in (avg ERA L7 {avg_bp_era:.2f})")

        # Park factor
        home_team = game.get("homeTeam", "") or game.get("home_team", "")
        pf = PARK_FACTORS.get(home_team)
        if pf is not None:
            if pf >= 105:
                lean += 1.0
                factors.append(f"Hitter-friendly park (PF {pf})")
            elif pf >= 102:
                lean += 0.4
                factors.append(f"Mildly hitter-friendly park (PF {pf})")
            elif pf <= 94:
                lean -= 0.8
                factors.append(f"Pitcher-friendly park (PF {pf})")
            elif pf <= 97:
                lean -= 0.3
                factors.append(f"Mildly pitcher-friendly park (PF {pf})")

        # Weather
        wx = game.get("weather") or {}
        if wx:
            temp_raw = wx.get("temp")
            wind_raw = (wx.get("wind", "") or "").lower()
            condition = (wx.get("condition", "") or "").lower()
            try:
                temp = int(temp_raw) if temp_raw is not None else None
            except (TypeError, ValueError):
                temp = None

            wind_out = "out" in wind_raw
            wind_in = " in" in wind_raw or wind_raw.startswith("in ")
            wind_mph = 0
            for part in wind_raw.replace(",", " ").split():
                try:
                    wind_mph = int(part)
                    break
                except ValueError:
                    continue

            if "dome" not in condition and "roof closed" not in condition:
                if temp is not None:
                    if temp >= 85:
                        lean += 0.5
                        factors.append(f"Hot weather ({temp}F)")
                    elif temp <= 45:
                        lean -= 0.5
                        factors.append(f"Cold weather ({temp}F)")
                if wind_out and wind_mph >= 10:
                    lean += 0.8
                    factors.append(f"Wind blowing out {wind_mph}mph")
                elif wind_out and wind_mph >= 5:
                    lean += 0.4
                    factors.append(f"Wind blowing out {wind_mph}mph (moderate)")
                elif wind_in and wind_mph >= 10:
                    lean -= 0.8
                    factors.append(f"Wind blowing in {wind_mph}mph")
                elif wind_in and wind_mph >= 5:
                    lean -= 0.4
                    factors.append(f"Wind blowing in {wind_mph}mph (moderate)")

        # Umpire
        ump = game.get("umpire") or {}
        ump_name = ump.get("name", "")
        if ump_name:
            tend = UMPIRE_TENDENCIES.get(ump_name)
            if tend:
                k_delta = tend["k_pct"] - LEAGUE_AVG_K_PCT
                if k_delta >= 0.8:
                    lean -= 0.5
                    factors.append(f"Tight-zone ump {ump_name} (K% {tend['k_pct']})")
                elif k_delta <= -0.5:
                    lean += 0.4
                    factors.append(f"Loose-zone ump {ump_name} (K% {tend['k_pct']})")

    elif sport in ("NBA", "WNBA", "NCAAB"):
        # Three-point rate proxy — high-scoring teams in fast pace = OVER
        if home_ppg and away_ppg:
            if sport == "NBA":
                if home_ppg >= 118 and away_ppg >= 118:
                    lean += 0.7
                    factors.append("Both teams elite offense (NBA 118+ PPG)")
                elif home_ppg >= 112 and away_ppg >= 112:
                    lean += 0.3
                    factors.append("Both above-avg scorers")
            elif sport == "NCAAB":
                if home_ppg >= 78 and away_ppg >= 78:
                    lean += 0.6
                    factors.append("Both teams high-scoring (NCAAB 78+ PPG)")

        # B2B fatigue — tired teams score less AND defend worse (slight wash, lean UNDER)
        if home_b2b and away_b2b:
            lean -= 0.2
            factors.append("Both on B2B — overall scoring depressed")
        elif home_b2b or away_b2b:
            lean -= 0.15
            factors.append("One team on B2B — slight scoring dip")

        # Defensive matchup
        if home_opp_ppg and away_opp_ppg:
            if sport == "NBA":
                if home_opp_ppg <= 108 and away_opp_ppg <= 108:
                    lean -= 0.7
                    factors.append("Both elite defenses (allow <108)")
                elif home_opp_ppg >= 118 and away_opp_ppg >= 118:
                    lean += 0.7
                    factors.append("Both porous defenses (allow 118+)")

    elif sport == "NHL":
        # Goalie quality
        home_g = home.get("starting_goalie", {}) or {}
        away_g = away.get("starting_goalie", {}) or {}
        home_gname = home_g.get("name") or home.get("recent_starter") or home.get("goalie")
        away_gname = away_g.get("name") or away.get("recent_starter") or away.get("goalie")

        if home_gname and away_gname:
            home_tier = _goalie_tier(home_gname)
            away_tier = _goalie_tier(away_gname)
            tier_val = {"ELITE": -1.0, "GOOD": -0.4, None: 0}
            g_lean = tier_val.get(home_tier, 0) + tier_val.get(away_tier, 0)
            if abs(g_lean) >= 0.5:
                lean += g_lean
                h_label = home_tier or "UNKNOWN"
                a_label = away_tier or "UNKNOWN"
                factors.append(f"Goalie matchup: {h_label} vs {a_label} (lean {g_lean:+.1f})")

        # SV% — both struggling goalies lean OVER
        home_sv = _normalize_sv_pct(home_g.get("sv_pct") or home_g.get("SV%") or home_g.get("svp"))
        away_sv = _normalize_sv_pct(away_g.get("sv_pct") or away_g.get("SV%") or away_g.get("svp"))
        if home_sv is not None and away_sv is not None:
            avg_sv = (home_sv + away_sv) / 2
            if avg_sv < 0.900:
                lean += 0.6
                factors.append(f"Both goalies struggling (avg SV% {avg_sv:.3f})")
            elif avg_sv > 0.925:
                lean -= 0.5
                factors.append(f"Both goalies elite (avg SV% {avg_sv:.3f})")

        # Special teams
        home_pp = home.get("pp_pct")
        away_pp = away.get("pp_pct")
        home_pk = home.get("pk_pct")
        away_pk = away.get("pk_pct")
        if home_pp is not None and away_pp is not None:
            avg_pp = (home_pp + away_pp) / 2
            if avg_pp >= 24:
                lean += 0.4
                factors.append(f"Strong power plays (avg PP% {avg_pp:.1f})")
            elif avg_pp <= 17:
                lean -= 0.3
                factors.append(f"Weak power plays (avg PP% {avg_pp:.1f})")
        if home_pk is not None and away_pk is not None:
            avg_pk = (home_pk + away_pk) / 2
            if avg_pk <= 76:
                lean += 0.4
                factors.append(f"Weak penalty kills (avg PK% {avg_pk:.1f})")
            elif avg_pk >= 84:
                lean -= 0.3
                factors.append(f"Strong penalty kills (avg PK% {avg_pk:.1f})")

        # Shot quality / pace
        home_nhl = home.get("nhl_pace", {}) or {}
        away_nhl = away.get("nhl_pace", {}) or {}
        home_sf = home_nhl.get("shots_for_per_game")
        away_sf = away_nhl.get("shots_for_per_game")
        if home_sf and away_sf:
            avg_sf = (home_sf + away_sf) / 2
            if avg_sf >= 34:
                lean += 0.4
                factors.append(f"High shot volume (avg {avg_sf:.1f} SF/g)")
            elif avg_sf <= 28:
                lean -= 0.3
                factors.append(f"Low shot volume (avg {avg_sf:.1f} SF/g)")

    elif sport == "SOCCER":
        # Goalkeeper quality
        for side_name, prof in [("home", home), ("away", away)]:
            gk = prof.get("goalkeeper", {}) or {}
            sv_pct = gk.get("save_pct")
            if sv_pct is not None:
                if sv_pct >= 0.75:
                    lean -= 0.3
                    factors.append(f"{side_name.title()} GK elite (SV% {sv_pct:.2f})")
                elif sv_pct <= 0.60:
                    lean += 0.3
                    factors.append(f"{side_name.title()} GK poor (SV% {sv_pct:.2f})")

        # Defensive style — low-conceding teams
        if home_opp_ppg and away_opp_ppg:
            avg_concede = (home_opp_ppg + away_opp_ppg) / 2
            if avg_concede <= 0.8:
                lean -= 0.6
                factors.append(f"Both tight defenses (avg concede {avg_concede:.2f})")
            elif avg_concede >= 1.8:
                lean += 0.6
                factors.append(f"Both leaky defenses (avg concede {avg_concede:.2f})")

    elif sport in ("NFL", "NCAAF"):
        # Weather for outdoor NFL
        wx = game.get("weather") or {}
        if wx:
            condition = (wx.get("condition", "") or "").lower()
            temp_raw = wx.get("temp")
            wind_raw = (wx.get("wind", "") or "").lower()
            try:
                temp = int(temp_raw) if temp_raw is not None else None
            except (TypeError, ValueError):
                temp = None
            wind_mph = 0
            for part in wind_raw.replace(",", " ").split():
                try:
                    wind_mph = int(part)
                    break
                except ValueError:
                    continue
            if "dome" not in condition and "roof closed" not in condition:
                if temp is not None and temp <= 32:
                    lean -= 0.5
                    factors.append(f"Freezing conditions ({temp}F)")
                if wind_mph >= 15:
                    lean -= 0.4
                    factors.append(f"Strong wind ({wind_mph}mph) — suppresses passing")
                if "rain" in condition or "snow" in condition:
                    lean -= 0.3
                    factors.append(f"Precipitation ({condition})")

    # Clamp lean to -5..+5
    lean = max(-5.0, min(5.0, lean))

    # Convert lean to verdict
    confidence = min(95, int(abs(lean) * 15 + 30))
    if abs(lean) < 0.5:
        verdict = "SKIP"
        confidence = max(20, confidence - 20)
    elif lean > 0:
        verdict = "OVER"
    else:
        verdict = "UNDER"

    return {
        "verdict": verdict,
        "score": round(lean, 2),
        "confidence": confidence,
        "factors": factors,
        "total_line": total_line,
    }


def grade_both_sides(game: dict) -> dict:
    """Grade both home and away, pick the better side."""
    home = grade_game(game, "home")
    away = grade_game(game, "away")
    if home["score"] >= away["score"]:
        best = home
        best["pick_team"] = game.get("home", game.get("home_team", "Home"))
        pick_side = "home"
    else:
        best = away
        best["pick_team"] = game.get("away", game.get("away_team", "Away"))
        pick_side = "away"

    # Run grader profiles on the best side
    profiles = grade_profiles(game, pick_side)

    return {
        "home": home,
        "away": away,
        "best": best,
        "profiles": profiles,
    }


# ─── Grader Profiles (Sintonia, Edge, Renzo) ──────────────────────────────────

# Each profile re-weights the same variables differently
PROFILE_WEIGHTS = {
    "sintonia": {
        # Main matrix — balanced, weights everything
        "off_ranking": 1.2, "def_ranking": 1.2, "form": 1.0, "home_away": 1.0,
        "star_player": 1.1, "rest": 1.0, "ats": 0.9, "h2h": 0.8,
        "motivation": 0.8, "depth": 0.7, "line_movement": 0.6,
        "pace": 0.7, "road_trip": 0.6, "starting_pitcher": 0.9, "starter_depth": 1.2,
        "bullpen": 1.25, "lineup_vs_hand": 1.15, "pitcher_hitter_archetype": 1.15,
        "congestion": 1.2,
        "goalie": 1.3,
    },
    "edge": {
        # Situational — calendar, rest, travel, motivation
        "rest": 1.5, "road_trip": 1.4, "motivation": 1.3, "home_away": 1.2,
        "form": 1.0, "depth": 1.0, "line_movement": 0.9,
        "off_ranking": 0.7, "def_ranking": 0.7, "star_player": 0.8,
        "ats": 0.8, "h2h": 0.7, "pace": 0.5,
        "starting_pitcher": 0.7, "starter_depth": 1.1,
        "bullpen": 1.35, "lineup_vs_hand": 1.1, "pitcher_hitter_archetype": 1.1,
        "congestion": 1.4,
        "goalie": 1.0,
    },
    "renzo": {
        # Conservative — only bets strong edges, penalizes uncertainty
        "off_ranking": 1.3, "def_ranking": 1.3, "ats": 1.2, "form": 1.1,
        "line_movement": 1.0, "h2h": 1.0,
        "home_away": 0.8, "rest": 0.7, "star_player": 0.7,
        "motivation": 0.5, "depth": 0.5, "road_trip": 0.5,
        "pace": 0.4, "starting_pitcher": 0.85, "starter_depth": 1.2,
        "bullpen": 1.3, "lineup_vs_hand": 1.2, "pitcher_hitter_archetype": 1.2,
        "congestion": 0.8,
        "goalie": 1.3,
    },
}

# MLB-only new-age matrices distilled from the strongest (A/A-) round-table
# responses: center on run value, contact quality, and pitcher-lab style edges.
MLB_NEW_AGE_PROFILE_WEIGHTS = {
    "runvalue": {
        "off_ranking": 1.35, "lineup_vs_hand": 1.35, "def_ranking": 1.15,
        "bullpen": 1.35, "starter_depth": 1.20, "starting_pitcher": 0.75,
        "pitcher_hitter_archetype": 1.10, "park_factor": 1.00, "umpire": 0.80,
        "form": 0.95, "line_movement": 0.95, "ats": 0.85,
    },
    "statcast": {
        "lineup_vs_hand": 1.45, "pitcher_hitter_archetype": 1.35,
        "off_ranking": 1.20, "bullpen": 1.20, "starter_depth": 1.10,
        "starting_pitcher": 0.70, "park_factor": 1.10, "umpire": 0.90,
        "form": 0.90, "line_movement": 0.85, "ats": 0.75,
    },
    "pitchlab": {
        "bullpen": 1.45, "starter_depth": 1.30, "pitcher_hitter_archetype": 1.25,
        "starting_pitcher": 0.80, "def_ranking": 1.10, "lineup_vs_hand": 1.10,
        "off_ranking": 0.95, "park_factor": 0.95, "umpire": 1.00,
        "form": 0.85, "line_movement": 0.80, "ats": 0.70,
    },
}


def grade_profiles(game: dict, pick_side: str) -> dict:
    """Run all 3 grader profiles on a game. Returns {name: {grade, score, ...}}"""
    base = grade_game(game, pick_side)
    base_vars = base.get("variables", {})
    profiles = {}
    sport = (game.get("sport") or "").upper()

    profiles_to_use = dict(PROFILE_WEIGHTS)
    if sport == "MLB":
        profiles_to_use.update(MLB_NEW_AGE_PROFILE_WEIGHTS)

    for profile_name, multipliers in profiles_to_use.items():
        # Re-weight the base variables
        total_w = 0
        total_s = 0
        for var_name, var_data in base_vars.items():
            if not var_data.get("available", True):
                continue
            mult = multipliers.get(var_name, 1.0)
            adjusted_weight = var_data["weight"] * mult
            total_w += adjusted_weight * 10
            total_s += var_data["score"] * adjusted_weight

        composite = round(total_s / total_w * 10, 2) if total_w > 0 else 5.0

        # Apply chain bonus from base
        chain_bonus = base.get("chain_bonus", 0)
        # Renzo is conservative — halve chain bonus
        if profile_name == "renzo":
            chain_bonus *= 0.5
        # Edge amplifies situational chains
        elif profile_name == "edge":
            chain_bonus *= 1.2

        # DISABLED: chains zeroed until system is dialed in
        final = round(max(1.0, min(10.0, composite + 0.0)), 2)  # was: composite + chain_bonus
        grade = score_to_grade(final)

        profiles[profile_name] = {
            "grade": grade,
            "final": final,
            "composite": composite,
            "sizing": score_to_sizing(final),
            "chains_fired": base.get("chains_fired", []),
            "pick_side": pick_side,
        }

    # Also grade the OTHER side so each profile can show who they pick
    other_side = "away" if pick_side == "home" else "home"
    other_base = grade_game(game, other_side)
    other_vars = other_base.get("variables", {})

    for profile_name, multipliers in profiles_to_use.items():
        total_w = 0
        total_s = 0
        for var_name, var_data in other_vars.items():
            if not var_data.get("available", True):
                continue
            mult = multipliers.get(var_name, 1.0)
            adjusted_weight = var_data["weight"] * mult
            total_w += adjusted_weight * 10
            total_s += var_data["score"] * adjusted_weight
        other_composite = round(total_s / total_w * 10, 2) if total_w > 0 else 5.0
        # DISABLED: chains zeroed until system is dialed in
        other_final = round(max(1.0, min(10.0, other_composite + 0.0)), 2)  # was: + chain_bonus * profile_mult

        # Each profile picks the side with the higher score
        if profiles[profile_name]["final"] >= other_final:
            profiles[profile_name]["picks"] = pick_side
        else:
            profiles[profile_name]["picks"] = other_side
        profiles[profile_name]["margin"] = round(profiles[profile_name]["final"] - other_final, 2)

    # Add "crew" — random-weighted blend of all 3 profiles
    import random
    if len(profiles) >= 3:
        blend_weights = {name: random.uniform(0.2, 0.5) for name in profiles}
        total_w = sum(blend_weights.values())
        blend_weights = {k: v / total_w for k, v in blend_weights.items()}  # normalize to 1.0

        crew_final = sum(profiles[name]["final"] * blend_weights[name] for name in profiles)
        crew_final = round(max(1.0, min(10.0, crew_final)), 2)
        crew_grade = score_to_grade(crew_final)

        # Crew picks whichever side the majority of profiles pick
        side_votes = {}
        for name in profiles:
            side = profiles[name].get("picks", pick_side)
            side_votes[side] = side_votes.get(side, 0) + 1
        crew_pick = max(side_votes, key=side_votes.get)

        profiles["crew"] = {
            "grade": crew_grade,
            "final": crew_final,
            "composite": crew_final,
            "sizing": score_to_sizing(crew_final),
            "chains_fired": [],
            "picks": crew_pick,
            "margin": round(crew_final - 5.0, 2),
            "blend": {k: round(v, 2) for k, v in blend_weights.items()},
        }

    return profiles


# ─── MMA / Combat Sports Grading ──────────────────────────────────────────────
#
# Combat sports don't have team profiles, rest days, bullpens, etc. — they have
# fighter records, reach/stance/style, and a moneyline. So the combat grader
# runs its own path: it reads odds + optional fighter dicts (populated by
# services/mma_fighter.py) and returns the SAME shape as grade_both_sides so
# the downstream /api/analyze and frontend don't have to special-case it.


def _mma_record_score(fighter: dict | None) -> tuple[float, str]:
    """Score a fighter's career record on a 0-10 scale. Wins% + volume."""
    if not fighter or fighter.get("wins") is None:
        return 5.0, "no record data"
    wins = int(fighter.get("wins") or 0)
    losses = int(fighter.get("losses") or 0)
    total = wins + losses
    if total < 3:
        return 5.0, f"{wins}-{losses} (rookie, insufficient sample)"
    win_pct = wins / total
    # Shape: 50% = 5.0, 70% = 7.0, 85%+ = 8.5+, 100% = 9.5
    score = 2.0 + win_pct * 7.5
    # Volume bonus — veterans with 15+ fights edge up
    if total >= 20:
        score += 0.5
    elif total >= 15:
        score += 0.3
    score = max(3.0, min(9.5, score))
    return round(score, 1), f"{wins}-{losses} ({win_pct:.0%})"


def _mma_moneyline_score(ml_home: int, ml_away: int) -> tuple[float, str, int]:
    """Score the competitiveness of the matchup by ML gap. Returns (score, note, gap)."""
    if not ml_home or not ml_away:
        return 5.0, "no ML data", 0
    gap = abs(ml_home - ml_away)
    if gap < 80:
        return 8.0, f"coin-flip (gap {gap})", gap
    if gap < 150:
        return 7.3, f"competitive (gap {gap})", gap
    if gap < 250:
        return 6.5, f"clear favorite (gap {gap})", gap
    if gap < 400:
        return 5.5, f"one-sided (gap {gap})", gap
    return 4.5, f"mismatch (gap {gap})", gap


def _mma_line_value_score(ml_home: int, ml_away: int, side: str) -> tuple[float, str]:
    """Score the line-value on picking a given side. Dogs with plus money
    are higher-value spots than favorites grinding out juice."""
    if not ml_home or not ml_away:
        return 5.0, "no ML"
    side_ml = ml_home if side == "home" else ml_away
    if side_ml > 200:
        return 7.5, f"plus-money dog ({side_ml:+d}, upside)"
    if side_ml > 100:
        return 6.8, f"live dog ({side_ml:+d})"
    if side_ml > -150:
        return 6.2, f"near pick'em ({side_ml:+d})"
    if side_ml > -250:
        return 5.5, f"moderate chalk ({side_ml:+d})"
    return 4.5, f"heavy chalk ({side_ml:+d})"


def _mma_style_score(fighter: dict | None, opp: dict | None) -> tuple[float, str]:
    """Very coarse style scoring from stance / weight class. Until fight-by-
    fight striking + TD data is in the profile, this is a placeholder that
    just returns a neutral score when nothing is known — NOT a fake signal."""
    if not fighter:
        return 5.0, "no style data"
    stance = (fighter.get("stance") or "").lower()
    opp_stance = ((opp or {}).get("stance") or "").lower()
    if not stance:
        return 5.0, "no stance data"
    # Southpaw vs orthodox is a known real edge for the southpaw in MMA.
    if stance == "southpaw" and opp_stance == "orthodox":
        return 6.3, "southpaw vs orthodox (slight edge)"
    if stance == "orthodox" and opp_stance == "southpaw":
        return 4.7, "orthodox vs southpaw (slight disadvantage)"
    return 5.5, f"stance: {stance}"


def _grade_mma_side(game: dict, side: str) -> dict:
    """Grade one fighter (home or away). Mirrors grade_game() return shape."""
    odds = game.get("odds", {}) or {}
    ml_home = int(odds.get("mlHome") or 0)
    ml_away = int(odds.get("mlAway") or 0)

    home_f = game.get("home_fighter") or {}
    away_f = game.get("away_fighter") or {}
    fighter = home_f if side == "home" else away_f
    opp = away_f if side == "home" else home_f

    record_s, record_n = _mma_record_score(fighter)
    opp_record_s, _ = _mma_record_score(opp)
    ml_s, ml_n, ml_gap = _mma_moneyline_score(ml_home, ml_away)
    line_s, line_n = _mma_line_value_score(ml_home, ml_away, side)
    style_s, style_n = _mma_style_score(fighter, opp)

    # Favorite bonus: if this side IS the ML favorite, their "form" variable
    # gets a nudge because the market is usually right on UFC ML.
    side_ml = ml_home if side == "home" else ml_away
    other_ml = ml_away if side == "home" else ml_home
    is_fav = side_ml and other_ml and side_ml < other_ml
    form_s = round(min(9.5, record_s + (0.5 if is_fav else -0.3)), 1) if record_s else 5.0
    form_n = f"{record_n}{' (favorite)' if is_fav else ''}"

    # Record vs opponent — delta in win %
    matchup_s = 5.0
    matchup_n = "insufficient data"
    if record_s > 5.0 and opp_record_s > 5.0:
        delta = record_s - opp_record_s
        matchup_s = round(max(3.0, min(9.0, 5.0 + delta * 0.8)), 1)
        matchup_n = f"record delta {delta:+.1f}"

    # Variables table matches the team-sport shape so downstream code reading
    # game["ourGrade"]["variables"] doesn't blow up.
    variables = {
        "form":         {"score": form_s,    "weight": 9, "weighted": round(form_s * 9, 1),    "note": form_n,    "available": record_s != 5.0},
        "off_ranking":  {"score": matchup_s, "weight": 8, "weighted": round(matchup_s * 8, 1), "note": matchup_n, "available": matchup_s != 5.0},
        "def_ranking":  {"score": matchup_s, "weight": 8, "weighted": round(matchup_s * 8, 1), "note": matchup_n, "available": matchup_s != 5.0},
        "moneyline_gap":{"score": ml_s,      "weight": 7, "weighted": round(ml_s * 7, 1),      "note": ml_n,      "available": ml_gap != 0},
        "line_value":   {"score": line_s,    "weight": 7, "weighted": round(line_s * 7, 1),    "note": line_n,    "available": bool(side_ml)},
        "style":        {"score": style_s,   "weight": 5, "weighted": round(style_s * 5, 1),   "note": style_n,   "available": style_s != 5.0},
    }

    active = {k: v for k, v in variables.items() if v.get("available", True)}
    total_weighted = sum(v["weighted"] for v in active.values())
    max_possible = sum(v["weight"] * 10 for v in active.values())
    composite = round(total_weighted / max_possible * 10, 2) if max_possible > 0 else 5.0

    # Small chain: favorite with strong record + competitive line = high conviction
    chain_bonus = 0.0
    chains_fired: list[str] = []
    if is_fav and record_s >= 7.0 and ml_gap and ml_gap < 250:
        chain_bonus += 0.4
        chains_fired.append("favorite_sharp_record")
    if line_s >= 7.0 and record_s >= 6.5:
        chain_bonus += 0.3
        chains_fired.append("live_dog_with_record")
    chain_bonus = max(-1.0, min(1.0, chain_bonus))

    # DISABLED: chains zeroed until system is dialed in
    final = round(max(1.0, min(10.0, composite + 0.0)), 2)  # was: composite + chain_bonus
    grade = score_to_grade(final)

    return {
        "grade": grade,
        "score": final,
        "composite": composite,
        "chain_bonus": chain_bonus,
        "chains_fired": chains_fired,
        "sizing": score_to_sizing(final),
        "confidence": min(95, max(40, int(55 + (final - 5) * 8))),
        "variables": variables,
        "pick_side": side,
    }


# Three MMA grader profiles — each re-weights the same variables differently.
# Mirrors how PROFILE_WEIGHTS works for team sports.
MMA_PROFILE_WEIGHTS = {
    "odds_sharp": {
        # Market-first. Trusts ML gap + line value over record.
        "moneyline_gap": 1.5, "line_value": 1.4, "form": 0.9,
        "off_ranking": 0.7, "def_ranking": 0.7, "style": 0.5,
    },
    "form_scout": {
        # Record/form first. Downweights line value.
        "form": 1.6, "off_ranking": 1.2, "def_ranking": 1.2,
        "moneyline_gap": 0.8, "line_value": 0.6, "style": 0.7,
    },
    "finisher": {
        # Style + stance matchup first. For coin-flip fights where market
        # pricing is weak.
        "style": 1.5, "form": 1.1, "moneyline_gap": 1.0,
        "off_ranking": 0.9, "def_ranking": 0.9, "line_value": 0.9,
    },
}


def _mma_profiles(game: dict, pick_side: str) -> dict:
    """Run all 3 MMA grader profiles on a fight. Returns same shape as
    grade_profiles() — {name: {grade, final, composite, sizing, chains_fired,
    pick_side, picks, margin}} plus a 'crew' blend."""
    base = _grade_mma_side(game, pick_side)
    base_vars = base.get("variables", {})
    other_side = "away" if pick_side == "home" else "home"
    other_base = _grade_mma_side(game, other_side)
    other_vars = other_base.get("variables", {})

    profiles: dict = {}
    for name, multipliers in MMA_PROFILE_WEIGHTS.items():
        # Pick-side composite
        tw, ts = 0.0, 0.0
        for var_name, var_data in base_vars.items():
            if not var_data.get("available", True):
                continue
            mult = multipliers.get(var_name, 1.0)
            w = var_data["weight"] * mult
            tw += w * 10
            ts += var_data["score"] * w
        composite = round(ts / tw * 10, 2) if tw > 0 else 5.0
        # DISABLED: chains zeroed until system is dialed in
        final = round(max(1.0, min(10.0, composite + 0.0)), 2)  # was: + chain_bonus

        # Other-side composite (so the profile can pick a side)
        otw, ots = 0.0, 0.0
        for var_name, var_data in other_vars.items():
            if not var_data.get("available", True):
                continue
            mult = multipliers.get(var_name, 1.0)
            w = var_data["weight"] * mult
            otw += w * 10
            ots += var_data["score"] * w
        other_composite = round(ots / otw * 10, 2) if otw > 0 else 5.0
        # DISABLED: chains zeroed until system is dialed in
        other_final = round(max(1.0, min(10.0, other_composite + 0.0)), 2)  # was: + chain_bonus

        picks = pick_side if final >= other_final else other_side
        profiles[name] = {
            "grade": score_to_grade(final),
            "final": final,
            "composite": composite,
            "sizing": score_to_sizing(final),
            "chains_fired": base.get("chains_fired", []),
            "pick_side": pick_side,
            "picks": picks,
            "margin": round(final - other_final, 2),
        }

    # Crew blend — equal-weighted for MMA since we only have 3 profiles
    if len(profiles) >= 3:
        blend_weights = {name: 1.0 / len(profiles) for name in profiles}
        crew_final = round(sum(profiles[n]["final"] * blend_weights[n] for n in profiles), 2)
        crew_final = round(max(1.0, min(10.0, crew_final)), 2)
        side_votes: dict = {}
        for name in profiles:
            s = profiles[name].get("picks", pick_side)
            side_votes[s] = side_votes.get(s, 0) + 1
        crew_pick = max(side_votes, key=side_votes.get)
        profiles["crew"] = {
            "grade": score_to_grade(crew_final),
            "final": crew_final,
            "composite": crew_final,
            "sizing": score_to_sizing(crew_final),
            "chains_fired": [],
            "picks": crew_pick,
            "margin": round(crew_final - 5.0, 2),
            "blend": {k: round(v, 2) for k, v in blend_weights.items()},
        }
    return profiles


def grade_mma_fight(game: dict) -> dict:
    """Top-level MMA/Boxing grader. Shape matches grade_both_sides() so the
    /api/analyze caller can use the same unpacking path for every sport.

    Inputs (on the game dict):
      - odds.mlHome / odds.mlAway  (required for any real signal)
      - home_fighter / away_fighter  (optional; populated by
        services/mma_fighter.py — record, stance, weight class)
      - homeTeam / awayTeam (fighter names)

    Output:
      {home, away, best, profiles}  — exactly like grade_both_sides
    """
    home = _grade_mma_side(game, "home")
    away = _grade_mma_side(game, "away")
    if home["score"] >= away["score"]:
        best = dict(home)
        best["pick_team"] = game.get("homeTeam") or game.get("home_team", "Home Fighter")
        pick_side = "home"
    else:
        best = dict(away)
        best["pick_team"] = game.get("awayTeam") or game.get("away_team", "Away Fighter")
        pick_side = "away"

    profiles = _mma_profiles(game, pick_side)

    return {
        "home": home,
        "away": away,
        "best": best,
        "profiles": profiles,
    }


# ─── Expected Value Calculator ────────────────────────────────────────────────


def ml_to_implied_prob(ml: int | float | None) -> float | None:
    """Convert American moneyline to implied probability."""
    if ml is None:
        return None
    if ml > 0:
        return 100 / (ml + 100)
    elif ml < 0:
        return abs(ml) / (abs(ml) + 100)
    return 0.5


def grade_to_true_prob(final_score: float, implied_prob: float | None = None) -> float:
    """
    Convert consensus grade score to estimated true win probability.
    Grade 5.0 = market is right, 7.0+ = market undervalues, 3.0- = market overvalues.
    Each point of deviation = ~3% edge.
    """
    if implied_prob is None:
        prob = 0.30 + (final_score / 10) * 0.45
        return max(0.25, min(0.80, prob))
    deviation = final_score - 5.0
    edge = deviation * 0.03
    true_prob = implied_prob + edge
    return max(0.15, min(0.90, true_prob))


def calculate_ev(game: dict, pick_side: str, consensus_final: float, pick: dict | None = None) -> dict:
    """
    Calculate expected value for a pick.
    Branches by pick type: spread picks price against the spread juice (cover prob),
    moneyline picks price against the ML (win prob). Mixing them produces nonsense
    (e.g. -3500 ML vs a -18 spread looks like -7% EV when the spread itself is +EV).
    """
    odds = game.get("odds", {})
    pick_type = (pick or {}).get("type", "ml")

    if pick_type == "total":
        if pick_side in ("over", "OVER"):
            ml = odds.get("overPrice") or -110
        else:
            ml = odds.get("underPrice") or -110
    elif pick_type == "spread":
        # Use the spread price for the pick side (default -110 if missing)
        if pick_side == "home":
            ml = odds.get("spreadPriceHome") or -110
        else:
            ml = odds.get("spreadPriceAway") or -110
    else:
        if pick_side == "home":
            ml = odds.get("mlHome") or odds.get("home_ml_current") or odds.get("ml_home")
        else:
            ml = odds.get("mlAway") or odds.get("away_ml_current") or odds.get("ml_away")

    implied_prob = ml_to_implied_prob(ml)
    # For spread picks, true_prob is interpreted as cover probability (anchored on
    # the ~52.4% spread implied), not win probability against the ML.
    true_prob = grade_to_true_prob(consensus_final, implied_prob)

    if implied_prob is None or ml is None or ml == 0:
        return {
            "ev_pct": None,
            "ev_grade": "N/A",
            "kelly_units": "N/A",
            "true_prob": None,
            "implied_prob": None,
            "edge": None,
            "moneyline": None,
        }

    # Decimal odds
    if ml > 0:
        decimal_odds = 1 + (ml / 100)
    else:
        decimal_odds = 1 + (100 / abs(ml))

    b = decimal_odds - 1  # Net odds
    p = true_prob
    q = 1 - p

    # EV calculation
    ev = (p * b) - q
    ev_pct = round(ev * 100, 2)

    # Kelly criterion (quarter Kelly)
    kelly_full = (b * p - q) / b if b > 0 else 0
    kelly_quarter = max(0, kelly_full * 0.25)

    # Kelly to units
    if kelly_quarter >= 0.06:
        kelly_units = "2u"
    elif kelly_quarter >= 0.04:
        kelly_units = "1.5u"
    elif kelly_quarter >= 0.02:
        kelly_units = "1u"
    elif kelly_quarter > 0:
        kelly_units = "0.5u"
    else:
        kelly_units = "PASS"

    # EV grade
    if ev_pct >= 10:
        ev_grade = "A+"
    elif ev_pct >= 7:
        ev_grade = "A"
    elif ev_pct >= 5:
        ev_grade = "B+"
    elif ev_pct >= 3:
        ev_grade = "B"
    elif ev_pct >= 0:
        ev_grade = "C"
    else:
        ev_grade = "F"

    return {
        "ev_pct": ev_pct,
        "ev_grade": ev_grade,
        "kelly_units": kelly_units,
        "true_prob": round(true_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "edge": round(true_prob - implied_prob, 4),
        "moneyline": ml,
    }


# ─── Peter's Rules ───────────────────────────────────────────────────────────


def peter_rules(game: dict, pick_side: str) -> dict:
    """
    Peter's hard rules — kill/boost/downgrade flags that override or adjust consensus.
    Rule 1: Big fav ATS trap
    Rule 2: Fresh injury boost
    Rule 3: Established injury priced
    Rule 4: Massive NCAAB spread
    """
    sport = (game.get("sport", "") or "").upper()
    odds = game.get("odds", {})
    opp_side = "away" if pick_side == "home" else "home"
    opp_profile = game.get(f"{opp_side}_profile", {})
    opp_injuries = game.get("injuries", {}).get(opp_side, [])

    flags = []
    adjustment = 0.0

    spread = odds.get("spread", odds.get("spread_home", 0)) or 0
    abs_spread = abs(spread)

    # Sport-specific thresholds
    big_fav_spread = {
        "NBA": 15, "WNBA": 12, "NCAAB": 20, "NCAAF": 21,
        "NHL": 2.5, "MLB": 2.5, "NFL": 14, "SOCCER": 2.5,
    }.get(sport, 15)
    star_ppg = {
        "NBA": 15, "WNBA": 15, "NCAAB": 12, "NCAAF": 0,
        "NHL": 0.8, "MLB": 0, "NFL": 0, "SOCCER": 0.3,
    }.get(sport, 15)

    # Rule 1: REMOVED — Peter no longer cares about spread size as a kill trigger
    opp_record = opp_profile.get("record", "0-0")
    opp_w, opp_l = _parse_record(opp_record)
    opp_pct = opp_w / max(opp_w + opp_l, 1)

    # Rule 2: Fresh injury boost — star OUT < 3 days, books may not have adjusted
    for inj in opp_injuries:
        if (inj.get("status") == "OUT" and
            inj.get("freshness") == "FRESH" and
            star_ppg > 0 and (inj.get("ppg") or 0) >= star_ppg):
            flags.append({
                "rule": "Fresh Injury Boost",
                "action": "BOOST",
                "severity": "EDGE",
                "note": f"FRESH: {inj.get('player', '?')} ({inj.get('ppg')} PPG) OUT — books may lag",
            })
            adjustment += 1.0

    # Rule 3: Established injury = already priced in
    for inj in opp_injuries:
        if (inj.get("status") == "OUT" and
            inj.get("freshness") in ("ESTABLISHED", "SEASON") and
            star_ppg > 0 and (inj.get("ppg") or 0) >= star_ppg):
            flags.append({
                "rule": "Injury Already Priced",
                "action": "DOWNGRADE",
                "severity": "WARNING",
                "note": f"PRICED: {inj.get('player', '?')} ({inj.get('ppg')} PPG) out long — team adapted",
            })
            adjustment -= 0.5

    # Rule 4: REMOVED — Peter no longer cares about spread size

    has_kill = any(f["action"] == "KILL" for f in flags)

    return {
        "flags": flags,
        "adjustment": round(adjustment, 1),
        "has_kill": has_kill,
    }
