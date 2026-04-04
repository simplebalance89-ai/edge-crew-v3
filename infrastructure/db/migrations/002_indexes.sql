-- ============================================================================
-- Migration: 002_indexes
-- Description: Performance indexes for Edge Crew v3.0
-- Created: 2026-04-04
-- ============================================================================

BEGIN;

-- ============================================================================
-- GAMES TABLE INDEXES
-- ============================================================================

-- Primary lookup by scheduled time
CREATE INDEX IF NOT EXISTS idx_games_scheduled 
    ON games(scheduled_at DESC);

-- Sport-based queries
CREATE INDEX IF NOT EXISTS idx_games_sport_status 
    ON games(sport, status);

-- Team lookups
CREATE INDEX IF NOT EXISTS idx_games_home_team 
    ON games(home_team);

CREATE INDEX IF NOT EXISTS idx_games_away_team 
    ON games(away_team);

-- Combined scheduled + sport for daily schedules
CREATE INDEX IF NOT EXISTS idx_games_schedule_sport 
    ON games(scheduled_at, sport) 
    WHERE status IN ('scheduled', 'live');

-- Status-based queries
CREATE INDEX IF NOT EXISTS idx_games_status_scheduled 
    ON games(scheduled_at) 
    WHERE status = 'scheduled';

-- ============================================================================
-- ODDS_HISTORY TABLE INDEXES
-- ============================================================================

-- Main query: odds by game and time
CREATE INDEX IF NOT EXISTS idx_odds_game_time 
    ON odds_history(game_id, time DESC);

-- Bookmaker-specific queries
CREATE INDEX IF NOT EXISTS idx_odds_bookmaker_time 
    ON odds_history(bookmaker, time DESC);

-- Combined game + bookmaker for specific bookmaker odds history
CREATE INDEX IF NOT EXISTS idx_odds_game_bookmaker 
    ON odds_history(game_id, bookmaker, time DESC);

-- Time-based range queries for backfills
CREATE INDEX IF NOT EXISTS idx_odds_time 
    ON odds_history(time DESC);

-- Recent odds fetch
CREATE INDEX IF NOT EXISTS idx_odds_fetched_at 
    ON odds_history(fetched_at DESC);

-- ============================================================================
-- GRADES TABLE INDEXES
-- ============================================================================

-- Main query: grades by game and time
CREATE INDEX IF NOT EXISTS idx_grades_game_time 
    ON grades(game_id, time DESC);

-- Confidence-based filtering
CREATE INDEX IF NOT EXISTS idx_grades_confidence 
    ON grades(consensus_confidence DESC) 
    WHERE consensus_confidence IS NOT NULL;

-- Convergence status queries
CREATE INDEX IF NOT EXISTS idx_grades_convergence 
    ON grades(game_id, convergence_status, time DESC);

-- Grade letter filtering
CREATE INDEX IF NOT EXISTS idx_grades_letter 
    ON grades(grade_letter, time DESC);

-- Time-series queries
CREATE INDEX IF NOT EXISTS idx_grades_time 
    ON grades(time DESC);

-- ============================================================================
-- MODEL_PERFORMANCE TABLE INDEXES
-- ============================================================================

-- Model-specific performance queries
CREATE INDEX IF NOT EXISTS idx_model_perf_model 
    ON model_performance(model_name, time DESC);

-- Sport + model combined
CREATE INDEX IF NOT EXISTS idx_model_perf_sport_model 
    ON model_performance(sport, model_name, time DESC);

-- Game-specific model results
CREATE INDEX IF NOT EXISTS idx_model_perf_game 
    ON model_performance(game_id, time DESC);

-- Accuracy tracking
CREATE INDEX IF NOT EXISTS idx_model_perf_accuracy 
    ON model_performance(model_name, accuracy DESC NULLS LAST);

-- Time-series queries
CREATE INDEX IF NOT EXISTS idx_model_perf_time 
    ON model_performance(time DESC);

-- ============================================================================
-- PICKS TABLE INDEXES
-- ============================================================================

-- Date-based pick queries
CREATE INDEX IF NOT EXISTS idx_picks_date 
    ON picks(created_at DESC);

-- Game + pick lookup
CREATE INDEX IF NOT EXISTS idx_picks_game 
    ON picks(game_id);

-- Result-based filtering (for performance tracking)
CREATE INDEX IF NOT EXISTS idx_picks_result 
    ON picks(result) 
    WHERE result IS NOT NULL;

-- Grade + confidence for quality analysis
CREATE INDEX IF NOT EXISTS idx_picks_grade_confidence 
    ON picks(grade, confidence DESC);

-- Active picks (pending results)
CREATE INDEX IF NOT EXISTS idx_picks_pending 
    ON picks(created_at) 
    WHERE result = 'pending';

-- Profit analysis
CREATE INDEX IF NOT EXISTS idx_picks_profit 
    ON picks(profit) 
    WHERE result IN ('win', 'loss', 'push');

-- ============================================================================
-- EDGE_OPPORTUNITIES TABLE INDEXES
-- ============================================================================

-- Active opportunities
CREATE INDEX IF NOT EXISTS idx_edge_active 
    ON edge_opportunities(detected_at DESC) 
    WHERE status = 'active';

-- Signal type filtering
CREATE INDEX IF NOT EXISTS idx_edge_signal_type 
    ON edge_opportunities(signal_type, confidence DESC);

-- Game-specific edges
CREATE INDEX IF NOT EXISTS idx_edge_game 
    ON edge_opportunities(game_id, detected_at DESC);

-- Confidence-based queries
CREATE INDEX IF NOT EXISTS idx_edge_confidence 
    ON edge_opportunities(confidence DESC) 
    WHERE status = 'active';

-- Expiration tracking
CREATE INDEX IF NOT EXISTS idx_edge_expires 
    ON edge_opportunities(expires_at) 
    WHERE status = 'active';

-- ============================================================================
-- LINE_MOVEMENTS TABLE INDEXES
-- ============================================================================

-- Movement tracking by game
CREATE INDEX IF NOT EXISTS idx_movements_game 
    ON line_movements(game_id, time DESC);

-- Significant movements only
CREATE INDEX IF NOT EXISTS idx_movements_significant 
    ON line_movements(time DESC) 
    WHERE ABS(delta) >= 1.0;

-- Bookmaker-specific movements
CREATE INDEX IF NOT EXISTS idx_movements_bookmaker 
    ON line_movements(bookmaker, time DESC);

-- Movement type filtering
CREATE INDEX IF NOT EXISTS idx_movements_type 
    ON line_movements(movement_type, time DESC);

-- Alert-triggered movements
CREATE INDEX IF NOT EXISTS idx_movements_alert 
    ON line_movements(time DESC) 
    WHERE triggered_alert = TRUE;

-- ============================================================================
-- REFERENCE TABLES INDEXES
-- ============================================================================

-- Teams lookups
CREATE INDEX IF NOT EXISTS idx_teams_sport 
    ON teams(sport, is_active);

CREATE INDEX IF NOT EXISTS idx_teams_abbrev 
    ON teams(abbreviation);

-- Bookmakers
CREATE INDEX IF NOT EXISTS idx_bookmakers_active 
    ON bookmakers(is_active, priority);

-- Sports config
CREATE INDEX IF NOT EXISTS idx_sports_active 
    ON sports(is_active);

-- ============================================================================
-- GIN INDEXES FOR JSONB COLUMNS
-- ============================================================================

-- Model performance metadata
CREATE INDEX IF NOT EXISTS idx_model_perf_metadata 
    ON model_performance USING GIN(metadata);

-- Grades model breakdown
CREATE INDEX IF NOT EXISTS idx_grades_breakdown 
    ON grades USING GIN(model_breakdown);

-- Edge opportunities metadata
CREATE INDEX IF NOT EXISTS idx_edge_metadata 
    ON edge_opportunities USING GIN(metadata);

-- Line movements metadata
CREATE INDEX IF NOT EXISTS idx_movements_metadata 
    ON line_movements USING GIN(metadata);

COMMIT;

-- ============================================================================
-- ANALYZE TABLES FOR QUERY PLANNER
-- ============================================================================

ANALYZE games;
ANALYZE odds_history;
ANALYZE grades;
ANALYZE model_performance;
ANALYZE picks;
ANALYZE edge_opportunities;
ANALYZE line_movements;
ANALYZE teams;
ANALYZE bookmakers;
ANALYZE sports;
