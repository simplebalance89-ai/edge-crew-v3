-- ============================================================================
-- Edge Crew v3.0 Database Schema
-- TimescaleDB for time-series analytics
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Games table - static game information
CREATE TABLE games (
    id TEXT PRIMARY KEY,
    sport TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' 
        CHECK (status IN ('scheduled', 'live', 'completed', 'postponed', 'cancelled')),
    home_score INTEGER,
    away_score INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- TIME-SERIES TABLES (Hypertables)
-- ============================================================================

-- Odds history - time-series tracking of betting odds
CREATE TABLE odds_history (
    time TIMESTAMPTZ NOT NULL,
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    bookmaker TEXT NOT NULL,
    spread DOUBLE PRECISION,
    total DOUBLE PRECISION,
    ml_home DOUBLE PRECISION,
    ml_away DOUBLE PRECISION,
    spread_home_odds INTEGER,
    spread_away_odds INTEGER,
    over_odds INTEGER,
    under_odds INTEGER,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('odds_history', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Grades history - time-series tracking of game grades/scores
CREATE TABLE grades (
    time TIMESTAMPTZ NOT NULL,
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    our_score DOUBLE PRECISION,
    ai_score DOUBLE PRECISION,
    consensus_score DOUBLE PRECISION,
    our_confidence DOUBLE PRECISION CHECK (our_confidence >= 0 AND our_confidence <= 1),
    ai_confidence DOUBLE PRECISION CHECK (ai_confidence >= 0 AND ai_confidence <= 1),
    consensus_confidence DOUBLE PRECISION CHECK (consensus_confidence >= 0 AND consensus_confidence <= 1),
    convergence_status TEXT CHECK (convergence_status IN ('aligned', 'divergent', 'uncertain', 'pending')),
    grade_letter TEXT CHECK (grade_letter IN ('A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F')),
    model_breakdown JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

SELECT create_hypertable('grades', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Model performance tracking - time-series metrics
CREATE TABLE model_performance (
    time TIMESTAMPTZ NOT NULL,
    model_name TEXT NOT NULL,
    sport TEXT NOT NULL,
    predicted_grade TEXT,
    actual_result BOOLEAN,
    error DOUBLE PRECISION,
    mse DOUBLE PRECISION,
    mae DOUBLE PRECISION,
    accuracy DOUBLE PRECISION,
    game_id TEXT REFERENCES games(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'
);

SELECT create_hypertable('model_performance', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Line movements - significant odds changes
CREATE TABLE line_movements (
    time TIMESTAMPTZ NOT NULL,
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    bookmaker TEXT NOT NULL,
    movement_type TEXT NOT NULL CHECK (movement_type IN ('spread', 'total', 'ml_home', 'ml_away')),
    old_value DOUBLE PRECISION NOT NULL,
    new_value DOUBLE PRECISION NOT NULL,
    delta DOUBLE PRECISION NOT NULL,
    percent_change DOUBLE PRECISION,
    triggered_alert BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'
);

SELECT create_hypertable('line_movements', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================================================
-- TRANSACTIONAL TABLES (Regular PostgreSQL tables)
-- ============================================================================

-- Picks - betting picks/selections
CREATE TABLE picks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    grade TEXT NOT NULL CHECK (grade IN ('A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F')),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    sizing DOUBLE PRECISION CHECK (sizing >= 0 AND sizing <= 5),
    odds_line DOUBLE PRECISION,
    odds_at_pick DOUBLE PRECISION,
    result TEXT CHECK (result IN ('win', 'loss', 'push', 'pending', 'void')),
    profit DOUBLE PRECISION DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resulted_at TIMESTAMPTZ
);

-- Edge opportunities - detected betting edges
CREATE TABLE edge_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL CHECK (signal_type IN (
        'reverse_line', 'injury_lag', 'sharp_money', 'public_fade', 
        'line_stall', 'opening_value', 'grading_divergence', 'consensus_edge'
    )),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    expected_value DOUBLE PRECISION,
    recommended_sizing DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'exploited', 'expired', 'voided')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bookmakers - supported sportsbooks
CREATE TABLE bookmakers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT,
    priority INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    api_endpoint TEXT,
    rate_limit INTEGER DEFAULT 60,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Teams - team reference data
CREATE TABLE teams (
    id TEXT PRIMARY KEY,
    sport TEXT NOT NULL,
    name TEXT NOT NULL,
    abbreviation TEXT NOT NULL,
    city TEXT,
    conference TEXT,
    division TEXT,
    logo_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(sport, abbreviation)
);

-- Sports configuration
CREATE TABLE sports (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    season_type TEXT,
    current_season INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    grading_weights JSONB DEFAULT '{}',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active games with latest grades
CREATE OR REPLACE VIEW v_games_with_latest_grade AS
SELECT 
    g.*,
    gr.grade_letter,
    gr.consensus_score,
    gr.consensus_confidence,
    gr.convergence_status,
    gr.time AS grade_time
FROM games g
LEFT JOIN LATERAL (
    SELECT *
    FROM grades
    WHERE game_id = g.id
    ORDER BY time DESC
    LIMIT 1
) gr ON TRUE
WHERE g.status IN ('scheduled', 'live');

-- Pick performance summary
CREATE OR REPLACE VIEW v_pick_performance AS
SELECT 
    sport,
    grade,
    COUNT(*) as total_picks,
    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
    SUM(CASE WHEN result = 'push' THEN 1 ELSE 0 END) as pushes,
    SUM(profit) as total_profit,
    AVG(confidence) as avg_confidence,
    AVG(CASE WHEN result = 'win' THEN confidence END) as avg_confidence_on_wins
FROM picks p
JOIN games g ON p.game_id = g.id
WHERE result IS NOT NULL
GROUP BY sport, grade;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Auto-update games.updated_at
CREATE TRIGGER update_games_updated_at
    BEFORE UPDATE ON games
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Calculate pick result based on game outcome
CREATE OR REPLACE FUNCTION calculate_pick_result(
    p_game_id TEXT,
    p_side TEXT,
    p_line DOUBLE PRECISION
) RETURNS TEXT AS $$
DECLARE
    v_game RECORD;
    v_result TEXT;
BEGIN
    SELECT * INTO v_game FROM games WHERE id = p_game_id;
    
    IF v_game.status != 'completed' THEN
        RETURN 'pending';
    END IF;
    
    -- Spread logic
    IF p_side IN ('home', 'away') THEN
        DECLARE
            v_spread_diff DOUBLE PRECISION;
        BEGIN
            IF p_side = 'home' THEN
                v_spread_diff := (v_game.home_score - v_game.away_score) + p_line;
            ELSE
                v_spread_diff := (v_game.away_score - v_game.home_score) + p_line;
            END IF;
            
            IF v_spread_diff > 0 THEN
                v_result := 'win';
            ELSIF v_spread_diff < 0 THEN
                v_result := 'loss';
            ELSE
                v_result := 'push';
            END IF;
        END;
    -- Total logic
    ELSIF p_side IN ('over', 'under') THEN
        DECLARE
            v_total INTEGER;
        BEGIN
            v_total := v_game.home_score + v_game.away_score;
            IF (p_side = 'over' AND v_total > p_line) OR (p_side = 'under' AND v_total < p_line) THEN
                v_result := 'win';
            ELSIF v_total = p_line THEN
                v_result := 'push';
            ELSE
                v_result := 'loss';
            END IF;
        END;
    END IF;
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- Detect significant line movements
CREATE OR REPLACE FUNCTION detect_line_movement()
RETURNS TRIGGER AS $$
DECLARE
    v_prev RECORD;
    v_delta DOUBLE PRECISION;
    v_percent DOUBLE PRECISION;
    v_threshold DOUBLE PRECISION := 0.5; -- Half point for spreads/totals
BEGIN
    -- Get previous odds for this game/bookmaker
    SELECT * INTO v_prev
    FROM odds_history
    WHERE game_id = NEW.game_id 
      AND bookmaker = NEW.bookmaker
      AND time < NEW.time
    ORDER BY time DESC
    LIMIT 1;
    
    -- Check spread movement
    IF v_prev IS NOT NULL AND NEW.spread IS NOT NULL AND v_prev.spread IS NOT NULL THEN
        v_delta := NEW.spread - v_prev.spread;
        IF ABS(v_delta) >= v_threshold THEN
            v_percent := CASE WHEN v_prev.spread != 0 
                THEN (v_delta / v_prev.spread) * 100 
                ELSE NULL END;
                
            INSERT INTO line_movements (
                time, game_id, bookmaker, movement_type,
                old_value, new_value, delta, percent_change
            ) VALUES (
                NEW.time, NEW.game_id, NEW.bookmaker, 'spread',
                v_prev.spread, NEW.spread, v_delta, v_percent
            );
        END IF;
    END IF;
    
    -- Check total movement
    IF v_prev IS NOT NULL AND NEW.total IS NOT NULL AND v_prev.total IS NOT NULL THEN
        v_delta := NEW.total - v_prev.total;
        IF ABS(v_delta) >= v_threshold THEN
            v_percent := CASE WHEN v_prev.total != 0 
                THEN (v_delta / v_prev.total) * 100 
                ELSE NULL END;
                
            INSERT INTO line_movements (
                time, game_id, bookmaker, movement_type,
                old_value, new_value, delta, percent_change
            ) VALUES (
                NEW.time, NEW.game_id, NEW.bookmaker, 'total',
                v_prev.total, NEW.total, v_delta, v_percent
            );
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for line movement detection
CREATE TRIGGER detect_line_movement_trigger
    AFTER INSERT ON odds_history
    FOR EACH ROW
    EXECUTE FUNCTION detect_line_move();

-- ============================================================================
-- CONTINUOUS AGGREGATES
-- ============================================================================

-- Hourly odds averages
CREATE MATERIALIZED VIEW odds_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS bucket,
    game_id,
    bookmaker,
    avg(spread) as avg_spread,
    avg(total) as avg_total,
    avg(ml_home) as avg_ml_home,
    avg(ml_away) as avg_ml_away,
    count(*) as sample_count,
    first(spread, time) as open_spread,
    last(spread, time) as close_spread
FROM odds_history
GROUP BY bucket, game_id, bookmaker
WITH NO DATA;

-- Daily grade summaries
CREATE MATERIALIZED VIEW grades_daily
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS bucket,
    game_id,
    avg(consensus_score) as avg_consensus_score,
    avg(consensus_confidence) as avg_consensus_confidence,
    mode() WITHIN GROUP (ORDER BY grade_letter) as mode_grade,
    mode() WITHIN GROUP (ORDER BY convergence_status) as mode_convergence
FROM grades
GROUP BY bucket, game_id
WITH NO DATA;

-- Model performance daily rollup
CREATE MATERIALIZED VIEW model_performance_daily
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS bucket,
    model_name,
    sport,
    count(*) as predictions,
    sum(CASE WHEN actual_result THEN 1 ELSE 0 END) as correct_predictions,
    avg(error) as avg_error,
    avg(mse) as avg_mse,
    avg(mae) as avg_mae,
    avg(accuracy) as avg_accuracy
FROM model_performance
GROUP BY bucket, model_name, sport
WITH NO DATA;

-- Add retention policies (optional - adjust based on requirements)
-- SELECT add_retention_policy('odds_history', INTERVAL '90 days');
-- SELECT add_retention_policy('grades', INTERVAL '365 days');

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE games IS 'Static game information and scheduling';
COMMENT ON TABLE odds_history IS 'Time-series of betting odds from various bookmakers';
COMMENT ON TABLE grades IS 'Time-series of AI-generated game grades and confidence scores';
COMMENT ON TABLE model_performance IS 'Time-series tracking of model prediction accuracy';
COMMENT ON TABLE picks IS 'Betting picks with results and profit tracking';
COMMENT ON TABLE edge_opportunities IS 'Detected betting edges and market inefficiencies';
COMMENT ON TABLE line_movements IS 'Significant line movements and market changes';
