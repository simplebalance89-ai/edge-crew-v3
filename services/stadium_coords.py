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


# NCAAF — top FBS programs by Odds API team naming. Not exhaustive (130+
# FBS teams + ~120 FCS); covers the schools that actually move on the
# Odds API slate. Add more as needed; lookup falls through to None on miss
# and weather just stays empty for those games.
NCAAF_STADIUMS: dict[str, tuple[float, float, bool]] = {
    "Alabama Crimson Tide":          (33.2083, -87.5504, False),  # Bryant-Denny
    "Auburn Tigers":                 (32.6024, -85.4892, False),  # Jordan-Hare
    "Georgia Bulldogs":              (33.9499, -83.3733, False),  # Sanford
    "Florida Gators":                (29.6500, -82.3486, False),  # The Swamp
    "LSU Tigers":                    (30.4119, -91.1839, False),  # Tiger Stadium
    "Tennessee Volunteers":          (35.9550, -83.9250, False),  # Neyland
    "Texas A&M Aggies":              (30.6100, -96.3408, False),  # Kyle Field
    "Arkansas Razorbacks":           (36.0683, -94.1786, False),  # Razorback
    "Ole Miss Rebels":               (34.3617, -89.5347, False),  # Vaught-Hemingway
    "Mississippi State Bulldogs":    (33.4564, -88.7944, False),  # Davis Wade
    "Missouri Tigers":               (38.9358, -92.3331, False),  # Faurot
    "South Carolina Gamecocks":      (33.9728, -81.0192, False),  # Williams-Brice
    "Kentucky Wildcats":             (38.0221, -84.5054, False),  # Kroger
    "Vanderbilt Commodores":         (36.1442, -86.8067, False),  # FirstBank
    "Texas Longhorns":               (30.2836, -97.7325, False),  # DKR
    "Oklahoma Sooners":              (35.2058, -97.4422, False),  # Memorial
    "Oklahoma State Cowboys":        (36.1256, -97.0656, False),  # Boone Pickens
    "Ohio State Buckeyes":           (40.0017, -83.0197, False),  # Ohio Stadium
    "Michigan Wolverines":           (42.2658, -83.7486, False),  # Big House
    "Michigan State Spartans":       (42.7281, -84.4842, False),  # Spartan Stadium
    "Penn State Nittany Lions":      (40.8122, -77.8567, False),  # Beaver
    "Wisconsin Badgers":             (43.0700, -89.4128, False),  # Camp Randall
    "Iowa Hawkeyes":                 (41.6586, -91.5511, False),  # Kinnick
    "Nebraska Cornhuskers":          (40.8206, -96.7056, False),  # Memorial
    "Minnesota Golden Gophers":      (44.9764, -93.2244, False),  # Huntington
    "Illinois Fighting Illini":      (40.0992, -88.2356, False),  # Memorial
    "Indiana Hoosiers":              (39.1808, -86.5256, False),  # Memorial
    "Purdue Boilermakers":           (40.4344, -86.9183, False),  # Ross-Ade
    "Northwestern Wildcats":         (42.0656, -87.6928, False),  # Ryan Field
    "Maryland Terrapins":            (38.9908, -76.9472, False),  # SECU
    "Rutgers Scarlet Knights":       (40.5136, -74.4658, False),  # SHI
    "USC Trojans":                   (34.0142, -118.2878, False), # LA Coliseum
    "UCLA Bruins":                   (34.1614, -118.1672, False), # Rose Bowl
    "Washington Huskies":            (47.6503, -122.3017, False), # Husky Stadium
    "Oregon Ducks":                  (44.0586, -123.0681, False), # Autzen
    "Oregon State Beavers":          (44.5594, -123.2811, False), # Reser
    "Washington State Cougars":      (46.7231, -117.1542, False), # Martin
    "Stanford Cardinal":             (37.4344, -122.1611, False), # Stanford
    "California Golden Bears":       (37.8717, -122.2508, False), # Memorial
    "Arizona Wildcats":              (32.2289, -110.9489, False), # Arizona Stadium
    "Arizona State Sun Devils":      (33.4264, -111.9325, False), # Mountain America
    "Utah Utes":                     (40.7600, -111.8489, False), # Rice-Eccles
    "Colorado Buffaloes":            (40.0094, -105.2669, False), # Folsom
    "Notre Dame Fighting Irish":     (41.6986, -86.2336, False),  # Notre Dame Stadium
    "Florida State Seminoles":       (30.4381, -84.3047, False),  # Doak Campbell
    "Miami Hurricanes":              (25.9580, -80.2389, False),  # Hard Rock
    "Clemson Tigers":                (34.6789, -82.8431, False),  # Memorial
    "North Carolina Tar Heels":      (35.9072, -79.0478, False),  # Kenan
    "NC State Wolfpack":             (35.8003, -78.7196, False),  # Carter-Finley
    "Duke Blue Devils":              (36.0014, -78.9419, False),  # Wallace Wade
    "Virginia Cavaliers":            (38.0317, -78.5147, False),  # Scott
    "Virginia Tech Hokies":          (37.2200, -80.4181, False),  # Lane
    "Wake Forest Demon Deacons":     (36.1336, -80.2547, False),  # Allegacy
    "Pittsburgh Panthers":           (40.4468, -80.0158, False),  # Acrisure
    "Louisville Cardinals":          (38.2058, -85.7589, False),  # L&N
    "Boston College Eagles":         (42.3350, -71.1664, False),  # Alumni
    "Syracuse Orange":                (43.0364, -76.1361, True),   # JMA Wireless Dome
    "Houston Cougars":               (29.7222, -95.3494, False),  # TDECU
    "TCU Horned Frogs":              (32.7100, -97.3686, False),  # Amon Carter
    "Baylor Bears":                  (31.5586, -97.1158, False),  # McLane
    "Texas Tech Red Raiders":        (33.5917, -101.8728, False), # Jones AT&T
    "Iowa State Cyclones":           (42.0142, -93.6358, False),  # Jack Trice
    "Kansas Jayhawks":               (38.9636, -95.2436, False),  # Memorial
    "Kansas State Wildcats":         (39.2019, -96.5942, False),  # Bill Snyder
    "West Virginia Mountaineers":    (39.6483, -79.9569, False),  # Milan Puskar
    "Cincinnati Bearcats":           (39.1311, -84.5158, False),  # Nippert
    "BYU Cougars":                   (40.2575, -111.6547, False), # LaVell Edwards
    "UCF Knights":                   (28.6081, -81.1925, False),  # FBC Mortgage
    "Memphis Tigers":                (35.1206, -89.8767, False),  # Simmons
    "Tulane Green Wave":             (29.9486, -90.1186, False),  # Yulman
    "SMU Mustangs":                  (32.8400, -96.7833, False),  # Gerald J. Ford
    "Navy Midshipmen":               (38.9853, -76.5114, False),  # Navy-Marine
    "Army Black Knights":            (41.3756, -73.9683, False),  # Michie
    "Air Force Falcons":             (38.9961, -104.8431, False), # Falcon
    "Boise State Broncos":           (43.6028, -116.1958, False), # Albertsons
    "Fresno State Bulldogs":         (36.8094, -119.7322, False), # Valley Children's
    "San Diego State Aztecs":        (32.7831, -117.1196, False), # Snapdragon
    "Hawaii Rainbow Warriors":       (21.3756, -157.9203, False), # Ching
    "Liberty Flames":                (37.3550, -79.1717, False),  # Williams
    "Appalachian State Mountaineers":(36.2114, -81.6856, False),  # Kidd Brewer
    "James Madison Dukes":           (38.4356, -78.8694, False),  # Bridgeforth
    "Coastal Carolina Chanticleers": (33.7958, -79.0125, False),  # Brooks
}


def lookup_ncaaf(home_team: str) -> tuple[float, float, bool] | None:
    """Return (lat, lon, dome) for the home team, or None if unknown."""
    return NCAAF_STADIUMS.get(home_team)
