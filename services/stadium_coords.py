"""
Stadium / venue coordinates for outdoor sports.

Used by services.weather_open_meteo to fetch real weather for NFL games
(and eventually NCAAF/Soccer if/when those team coord tables are filled in).
Indexed by team name as it comes back from the Odds API.

Domes are marked dome=True so callers can short-circuit weather fetching —
weather inside an enclosed stadium doesn't matter for the bet.
"""
from __future__ import annotations

# (lat, lon, dome) — coords are stadium center, decimal degrees
NFL_STADIUMS: dict[str, tuple[float, float, bool]] = {
    "Arizona Cardinals":      (33.5276, -112.2626, True),   # State Farm Stadium (retractable)
    "Atlanta Falcons":        (33.7553, -84.4006,  True),   # Mercedes-Benz Stadium (retractable)
    "Baltimore Ravens":       (39.2780, -76.6227,  False),  # M&T Bank
    "Buffalo Bills":          (42.7738, -78.7870,  False),  # Highmark
    "Carolina Panthers":      (35.2258, -80.8528,  False),  # Bank of America
    "Chicago Bears":          (41.8623, -87.6167,  False),  # Soldier Field
    "Cincinnati Bengals":     (39.0954, -84.5160,  False),  # Paycor
    "Cleveland Browns":       (41.5061, -81.6995,  False),  # Cleveland Browns Stadium
    "Dallas Cowboys":         (32.7473, -97.0945,  True),   # AT&T (retractable)
    "Denver Broncos":         (39.7439, -105.0201, False),  # Empower Field
    "Detroit Lions":          (42.3400, -83.0456,  True),   # Ford Field (dome)
    "Green Bay Packers":      (44.5013, -88.0622,  False),  # Lambeau
    "Houston Texans":         (29.6847, -95.4107,  True),   # NRG (retractable)
    "Indianapolis Colts":     (39.7601, -86.1639,  True),   # Lucas Oil (retractable)
    "Jacksonville Jaguars":   (30.3239, -81.6373,  False),  # EverBank
    "Kansas City Chiefs":     (39.0489, -94.4839,  False),  # Arrowhead
    "Las Vegas Raiders":      (36.0908, -115.1830, True),   # Allegiant (dome)
    "Los Angeles Chargers":   (33.9534, -118.3387, True),   # SoFi (dome)
    "Los Angeles Rams":       (33.9534, -118.3387, True),   # SoFi (dome)
    "Miami Dolphins":         (25.9580, -80.2389,  False),  # Hard Rock
    "Minnesota Vikings":      (44.9737, -93.2581,  True),   # U.S. Bank (dome)
    "New England Patriots":   (42.0909, -71.2643,  False),  # Gillette
    "New Orleans Saints":     (29.9509, -90.0815,  True),   # Caesars Superdome (dome)
    "New York Giants":        (40.8136, -74.0744,  False),  # MetLife
    "New York Jets":          (40.8136, -74.0744,  False),  # MetLife
    "Philadelphia Eagles":    (39.9008, -75.1675,  False),  # Lincoln Financial
    "Pittsburgh Steelers":    (40.4468, -80.0158,  False),  # Acrisure
    "San Francisco 49ers":    (37.4030, -121.9700, False),  # Levi's
    "Seattle Seahawks":       (47.5952, -122.3316, False),  # Lumen Field
    "Tampa Bay Buccaneers":   (27.9759, -82.5033,  False),  # Raymond James
    "Tennessee Titans":       (36.1665, -86.7713,  False),  # Nissan
    "Washington Commanders":  (38.9078, -76.8645,  False),  # FedExField
}


def lookup_nfl(home_team: str) -> tuple[float, float, bool] | None:
    """Return (lat, lon, dome) for the home team, or None if unknown."""
    return NFL_STADIUMS.get(home_team)
