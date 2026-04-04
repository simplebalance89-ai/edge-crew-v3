-- ============================================================================
-- Seed Data: Sports, Teams, and Bookmakers
-- Edge Crew v3.0
-- ============================================================================

BEGIN;

-- ============================================================================
-- SPORTS
-- ============================================================================

INSERT INTO sports (id, name, season_type, current_season, is_active, grading_weights, config) VALUES
('nba', 'NBA', 'regular', 2025, TRUE, 
    '{"offense": 0.25, "defense": 0.25, "pace": 0.15, "rest": 0.15, "matchup": 0.15, "market": 0.05}'::jsonb,
    '{"games_per_season": 82, "playoff_teams": 16, "conferences": ["East", "West"]}'::jsonb
),
('nfl', 'NFL', 'regular', 2025, TRUE,
    '{"offense": 0.30, "defense": 0.30, "special_teams": 0.10, "rest": 0.15, "matchup": 0.10, "market": 0.05}'::jsonb,
    '{"games_per_season": 17, "playoff_teams": 14, "conferences": ["AFC", "NFC"]}'::jsonb
),
('mlb', 'MLB', 'regular', 2025, TRUE,
    '{"offense": 0.25, "defense": 0.25, "pitching": 0.25, "bullpen": 0.15, "matchup": 0.10}'::jsonb,
    '{"games_per_season": 162, "playoff_teams": 12, "leagues": ["AL", "NL"]}'::jsonb
),
('nhl', 'NHL', 'regular', 2025, TRUE,
    '{"offense": 0.25, "defense": 0.25, "goaltending": 0.25, "special_teams": 0.15, "matchup": 0.10}'::jsonb,
    '{"games_per_season": 82, "playoff_teams": 16, "conferences": ["Eastern", "Western"]}'::jsonb
),
('ncaab', 'NCAAB', 'regular', 2025, TRUE,
    '{"offense": 0.25, "defense": 0.25, "pace": 0.20, "home_court": 0.20, "market": 0.10}'::jsonb,
    '{"conferences": ["ACC", "Big 12", "Big East", "Big Ten", "Pac-12", "SEC", "AAC", "A-10", "MWC", "WCC"]}'::jsonb
),
('ncaaf', 'NCAAF', 'regular', 2025, TRUE,
    '{"offense": 0.30, "defense": 0.30, "special_teams": 0.10, "recruiting": 0.15, "coaching": 0.15}'::jsonb,
    '{"fbs_teams": 134, "conferences": ["SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "AAC", "MWC", "MAC", "C-USA", "SBC"]}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    grading_weights = EXCLUDED.grading_weights,
    config = EXCLUDED.config,
    current_season = EXCLUDED.current_season;

-- ============================================================================
-- NBA TEAMS
-- ============================================================================

INSERT INTO teams (id, sport, name, abbreviation, city, conference, division, is_active) VALUES
('nba-atl', 'nba', 'Hawks', 'ATL', 'Atlanta', 'East', 'Southeast', TRUE),
('nba-bos', 'nba', 'Celtics', 'BOS', 'Boston', 'East', 'Atlantic', TRUE),
('nba-bkn', 'nba', 'Nets', 'BKN', 'Brooklyn', 'East', 'Atlantic', TRUE),
('nba-cha', 'nba', 'Hornets', 'CHA', 'Charlotte', 'East', 'Southeast', TRUE),
('nba-chi', 'nba', 'Bulls', 'CHI', 'Chicago', 'East', 'Central', TRUE),
('nba-cle', 'nba', 'Cavaliers', 'CLE', 'Cleveland', 'East', 'Central', TRUE),
('nba-dal', 'nba', 'Mavericks', 'DAL', 'Dallas', 'West', 'Southwest', TRUE),
('nba-den', 'nba', 'Nuggets', 'DEN', 'Denver', 'West', 'Northwest', TRUE),
('nba-det', 'nba', 'Pistons', 'DET', 'Detroit', 'East', 'Central', TRUE),
('nba-gsw', 'nba', 'Warriors', 'GSW', 'Golden State', 'West', 'Pacific', TRUE),
('nba-hou', 'nba', 'Rockets', 'HOU', 'Houston', 'West', 'Southwest', TRUE),
('nba-ind', 'nba', 'Pacers', 'IND', 'Indiana', 'East', 'Central', TRUE),
('nba-lac', 'nba', 'Clippers', 'LAC', 'LA', 'West', 'Pacific', TRUE),
('nba-lal', 'nba', 'Lakers', 'LAL', 'Los Angeles', 'West', 'Pacific', TRUE),
('nba-mem', 'nba', 'Grizzlies', 'MEM', 'Memphis', 'West', 'Southwest', TRUE),
('nba-mia', 'nba', 'Heat', 'MIA', 'Miami', 'East', 'Southeast', TRUE),
('nba-mil', 'nba', 'Bucks', 'MIL', 'Milwaukee', 'East', 'Central', TRUE),
('nba-min', 'nba', 'Timberwolves', 'MIN', 'Minnesota', 'West', 'Northwest', TRUE),
('nba-nop', 'nba', 'Pelicans', 'NOP', 'New Orleans', 'West', 'Southwest', TRUE),
('nba-nyk', 'nba', 'Knicks', 'NYK', 'New York', 'East', 'Atlantic', TRUE),
('nba-okc', 'nba', 'Thunder', 'OKC', 'Oklahoma City', 'West', 'Northwest', TRUE),
('nba-orl', 'nba', 'Magic', 'ORL', 'Orlando', 'East', 'Southeast', TRUE),
('nba-phi', 'nba', '76ers', 'PHI', 'Philadelphia', 'East', 'Atlantic', TRUE),
('nba-phx', 'nba', 'Suns', 'PHX', 'Phoenix', 'West', 'Pacific', TRUE),
('nba-por', 'nba', 'Trail Blazers', 'POR', 'Portland', 'West', 'Northwest', TRUE),
('nba-sac', 'nba', 'Kings', 'SAC', 'Sacramento', 'West', 'Pacific', TRUE),
('nba-sas', 'nba', 'Spurs', 'SAS', 'San Antonio', 'West', 'Southwest', TRUE),
('nba-tor', 'nba', 'Raptors', 'TOR', 'Toronto', 'East', 'Atlantic', TRUE),
('nba-uta', 'nba', 'Jazz', 'UTA', 'Utah', 'West', 'Northwest', TRUE),
('nba-was', 'nba', 'Wizards', 'WAS', 'Washington', 'East', 'Southeast', TRUE)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    city = EXCLUDED.city,
    conference = EXCLUDED.conference,
    division = EXCLUDED.division,
    is_active = EXCLUDED.is_active;

-- ============================================================================
-- BOOKMAKERS
-- ============================================================================

INSERT INTO bookmakers (id, name, region, priority, is_active, rate_limit) VALUES
('draftkings', 'DraftKings', 'US', 10, TRUE, 60),
('fanduel', 'FanDuel', 'US', 10, TRUE, 60),
('betmgm', 'BetMGM', 'US', 20, TRUE, 60),
('caesars', 'Caesars Sportsbook', 'US', 20, TRUE, 60),
('pointsbet', 'PointsBet', 'US', 30, TRUE, 60),
('bet365', 'bet365', 'US', 30, TRUE, 60),
('unibet', 'Unibet', 'US', 40, TRUE, 60),
('wynnbet', 'WynnBET', 'US', 50, TRUE, 60),
('barstool', 'Barstool Sportsbook', 'US', 40, TRUE, 60),
('bovada', 'Bovada', 'US', 25, TRUE, 60),
('pinnacle', 'Pinnacle', 'Global', 5, TRUE, 120),
('betfair', 'Betfair', 'Global', 15, TRUE, 60),
('williamhill', 'William Hill', 'UK', 20, TRUE, 60)
ON CONFLICT (id) DO UPDATE SET
    priority = EXCLUDED.priority,
    is_active = EXCLUDED.is_active,
    rate_limit = EXCLUDED.rate_limit;

COMMIT;
