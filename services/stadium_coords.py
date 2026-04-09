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


# Soccer — top European clubs + MLS regulars. Indexed by Odds API team
# names. Soccer stadiums are almost universally open-air; the dome flag is
# False for everything here. Lookups fall through to None for misses and
# weather just stays empty for those games.
SOCCER_STADIUMS: dict[str, tuple[float, float, bool]] = {
    # ── EPL ─────────────────────────────────────────────────────────────
    "Arsenal":                       (51.5549, -0.1084,  False),
    "Aston Villa":                   (52.5092, -1.8847,  False),
    "AFC Bournemouth":               (50.7351, -1.8383,  False),
    "Bournemouth":                   (50.7351, -1.8383,  False),
    "Brentford":                     (51.4906, -0.2887,  False),
    "Brighton and Hove Albion":      (50.8616, -0.0836,  False),
    "Brighton & Hove Albion":        (50.8616, -0.0836,  False),
    "Chelsea":                       (51.4817, -0.1910,  False),
    "Crystal Palace":                (51.3983, -0.0855,  False),
    "Everton":                       (53.4388, -2.9663,  False),
    "Fulham":                        (51.4750, -0.2217,  False),
    "Ipswich Town":                  (52.0550, 1.1448,   False),
    "Leicester City":                (52.6204, -1.1422,  False),
    "Liverpool":                     (53.4308, -2.9608,  False),
    "Manchester City":               (53.4831, -2.2004,  False),
    "Manchester United":             (53.4631, -2.2913,  False),
    "Newcastle United":              (54.9756, -1.6217,  False),
    "Nottingham Forest":             (52.9400, -1.1328,  False),
    "Southampton":                   (50.9059, -1.3914,  False),
    "Tottenham Hotspur":             (51.6043, -0.0664,  False),
    "West Ham United":               (51.5386, -0.0166,  False),
    "Wolverhampton Wanderers":       (52.5903, -2.1303,  False),
    # ── La Liga ────────────────────────────────────────────────────────
    "Real Madrid":                   (40.4531, -3.6883,  False),
    "Barcelona":                     (41.3809, 2.1228,   False),
    "Atletico Madrid":               (40.4361, -3.5994,  False),
    "Athletic Bilbao":               (43.2641, -2.9494,  False),
    "Real Sociedad":                 (43.3014, -1.9737,  False),
    "Real Betis":                    (37.3564, -5.9819,  False),
    "Sevilla":                       (37.3839, -5.9706,  False),
    "Villarreal":                    (39.9442, -0.1031,  False),
    "Valencia":                      (39.4747, -0.3583,  False),
    "Celta Vigo":                    (42.2119, -8.7397,  False),
    "Girona":                        (41.9614, 2.8281,   False),
    "Osasuna":                       (42.7969, -1.6369,  False),
    "Getafe":                        (40.3253, -3.7144,  False),
    "Mallorca":                      (39.5897, 2.6300,   False),
    "Las Palmas":                    (28.1003, -15.4564, False),
    "Rayo Vallecano":                (40.3914, -3.6589,  False),
    "Espanyol":                      (41.3475, 2.0700,   False),
    "Leganes":                       (40.3406, -3.7644,  False),
    "Alaves":                        (42.8372, -2.6878,  False),
    "Real Valladolid":               (41.6444, -4.7600,  False),
    # ── Serie A ────────────────────────────────────────────────────────
    "Inter Milan":                   (45.4781, 9.1240,   False),
    "AC Milan":                      (45.4781, 9.1240,   False),
    "Juventus":                      (45.1097, 7.6411,   False),
    "Napoli":                        (40.8278, 14.1933,  False),
    "Roma":                          (41.9342, 12.4547,  False),
    "Lazio":                         (41.9342, 12.4547,  False),
    "Atalanta":                      (45.7089, 9.6809,   False),
    "Fiorentina":                    (43.7806, 11.2825,  False),
    "Bologna":                       (44.4922, 11.3097,  False),
    "Torino":                        (45.0414, 7.6500,   False),
    "Udinese":                       (46.0814, 13.2003,  False),
    "Genoa":                         (44.4164, 8.9522,   False),
    "Hellas Verona":                 (45.4356, 10.9683,  False),
    "Cagliari":                      (39.1997, 9.1372,   False),
    "Empoli":                        (43.7261, 10.9550,  False),
    "Lecce":                         (40.3653, 18.2089,  False),
    "Monza":                         (45.5828, 9.3083,   False),
    "Parma":                         (44.7950, 10.3381,  False),
    "Como":                          (45.8147, 9.0764,   False),
    "Venezia":                       (45.4239, 12.3631,  False),
    # ── Bundesliga ─────────────────────────────────────────────────────
    "Bayern Munich":                 (48.2188, 11.6247,  False),
    "Borussia Dortmund":             (51.4925, 7.4519,   False),
    "RB Leipzig":                    (51.3458, 12.3481,  False),
    "Bayer Leverkusen":              (51.0383, 7.0025,   False),
    "Eintracht Frankfurt":           (50.0686, 8.6450,   False),
    "VfL Wolfsburg":                 (52.4322, 10.8033,  False),
    "Borussia Monchengladbach":      (51.1747, 6.3856,   False),
    "VfB Stuttgart":                 (48.7925, 9.2322,   False),
    "SC Freiburg":                   (48.0211, 7.8297,   False),
    "1899 Hoffenheim":               (49.2386, 8.8881,   False),
    "FC Augsburg":                   (48.3231, 10.8861,  False),
    "Werder Bremen":                 (53.0664, 8.8378,   False),
    "FC Union Berlin":               (52.4575, 13.5681,  False),
    "Mainz":                         (49.9844, 8.2244,   False),
    "Holstein Kiel":                 (54.3494, 10.1219,  False),
    "St Pauli":                      (53.5547, 9.9678,   False),
    "VfL Bochum":                    (51.4894, 7.2367,   False),
    "FC Heidenheim":                 (48.6764, 10.1453,  False),
    # ── Ligue 1 ────────────────────────────────────────────────────────
    "Paris Saint-Germain":           (48.8414, 2.2530,   False),
    "Marseille":                     (43.2697, 5.3958,   False),
    "Lyon":                          (45.7653, 4.9819,   False),
    "Lille":                         (50.6119, 3.1300,   False),
    "Monaco":                        (43.7283, 7.4156,   False),
    "Nice":                          (43.7053, 7.1925,   False),
    "Rennes":                        (48.1075, -1.7128,  False),
    "Lens":                          (50.4325, 2.8150,   False),
    "Strasbourg":                    (48.5600, 7.7544,   False),
    "Nantes":                        (47.2558, -1.5253,  False),
    "Toulouse":                      (43.5831, 1.4339,   False),
    "Reims":                         (49.2467, 4.0250,   False),
    "Brest":                         (48.4028, -4.4617,  False),
    "Montpellier":                   (43.6225, 3.8117,   False),
    "Auxerre":                       (47.7872, 3.5897,   False),
    "Angers":                        (47.4603, -0.5311,  False),
    "Le Havre":                      (49.4983, 0.1697,   False),
    "Saint-Etienne":                 (45.4608, 4.3900,   False),
    # ── MLS (selected) ─────────────────────────────────────────────────
    "Inter Miami CF":                (25.9580, -80.2389, False),
    "LAFC":                          (34.0125, -118.2853, False),
    "LA Galaxy":                     (33.8644, -118.2611, False),
    "Atlanta United FC":             (33.7553, -84.4006, True),  # Mercedes-Benz dome
    "Seattle Sounders FC":           (47.5952, -122.3316, False),
    "Portland Timbers":              (45.5214, -122.6919, False),
    "New York City FC":              (40.8296, -73.9262, False),
    "New York Red Bulls":            (40.7361, -74.1503, False),
    "Toronto FC":                    (43.6328, -79.4186, False),
    "CF Montreal":                   (45.5631, -73.5525, False),
    "Vancouver Whitecaps FC":        (49.2767, -123.1119, False),
    "Columbus Crew":                 (39.9683, -83.0167, False),
    "FC Cincinnati":                 (39.1117, -84.5222, False),
    "Philadelphia Union":            (39.8328, -75.3786, False),
    "DC United":                     (38.8689, -77.0125, False),
    "New England Revolution":        (42.0909, -71.2643, False),
    "Orlando City SC":               (28.5411, -81.3886, False),
    "Nashville SC":                  (36.1322, -86.7656, False),
    "FC Dallas":                     (33.1553, -96.8350, False),
    "Houston Dynamo FC":             (29.7522, -95.3528, False),
    "Sporting Kansas City":          (39.1219, -94.8228, False),
    "Colorado Rapids":               (39.8056, -104.8917, False),
    "Real Salt Lake":                (40.5831, -111.8931, False),
    "San Jose Earthquakes":          (37.3508, -121.9258, False),
    "Austin FC":                     (30.3886, -97.7194, False),
    "Charlotte FC":                  (35.2258, -80.8528, False),
    "Minnesota United FC":           (44.9531, -93.1656, False),
    "Chicago Fire FC":                (41.8623, -87.6167, False),
    "St. Louis City SC":             (38.6314, -90.2103, False),
}


def lookup_soccer(home_team: str) -> tuple[float, float, bool] | None:
    """Return (lat, lon, dome) for the home team, or None if unknown."""
    return SOCCER_STADIUMS.get(home_team)
