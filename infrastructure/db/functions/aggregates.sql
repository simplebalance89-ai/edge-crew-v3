-- ============================================================================
-- Custom Aggregate Functions for Edge Crew v3.0
-- TimescaleDB Analytics Functions
-- ============================================================================

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Calculate ROI from profit and implied probability
CREATE OR REPLACE FUNCTION calculate_roi(
    p_profit DOUBLE PRECISION,
    p_odds DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_implied_prob DOUBLE PRECISION;
BEGIN
    -- Convert American odds to implied probability
    IF p_odds > 0 THEN
        v_implied_prob := 100 / (p_odds + 100);
    ELSE
        v_implied_prob := ABS(p_odds) / (ABS(p_odds) + 100);
    END IF;
    
    -- Calculate ROI as profit percentage of expected risk
    IF v_implied_prob > 0 THEN
        RETURN p_profit / (1 / v_implied_prob);
    END IF;
    
    RETURN 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Convert American odds to decimal
CREATE OR REPLACE FUNCTION american_to_decimal(
    p_american_odds DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
BEGIN
    IF p_american_odds > 0 THEN
        RETURN (p_american_odds / 100) + 1;
    ELSE
        RETURN (100 / ABS(p_american_odds)) + 1;
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Convert decimal odds to American
CREATE OR REPLACE FUNCTION decimal_to_american(
    p_decimal_odds DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
BEGIN
    IF p_decimal_odds >= 2.0 THEN
        RETURN (p_decimal_odds - 1) * 100;
    ELSE
        RETURN -100 / (p_decimal_odds - 1);
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Calculate implied probability from American odds
CREATE OR REPLACE FUNCTION odds_to_probability(
    p_american_odds DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
BEGIN
    IF p_american_odds > 0 THEN
        RETURN 100 / (p_american_odds + 100);
    ELSE
        RETURN ABS(p_american_odds) / (ABS(p_american_odds) + 100);
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- GRADE CALCULATION FUNCTIONS
-- ============================================================================

-- Convert numeric score to letter grade
CREATE OR REPLACE FUNCTION score_to_grade(
    p_score DOUBLE PRECISION
) RETURNS TEXT AS $$
BEGIN
    RETURN CASE
        WHEN p_score >= 95 THEN 'A+'
        WHEN p_score >= 90 THEN 'A'
        WHEN p_score >= 87 THEN 'A-'
        WHEN p_score >= 83 THEN 'B+'
        WHEN p_score >= 80 THEN 'B'
        WHEN p_score >= 77 THEN 'B-'
        WHEN p_score >= 73 THEN 'C+'
        WHEN p_score >= 70 THEN 'C'
        WHEN p_score >= 67 THEN 'C-'
        WHEN p_score >= 63 THEN 'D+'
        WHEN p_score >= 60 THEN 'D'
        WHEN p_score >= 57 THEN 'D-'
        ELSE 'F'
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Calculate weighted grade from component scores
CREATE OR REPLACE FUNCTION calculate_weighted_grade(
    p_components JSONB,
    p_weights JSONB
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_total_weight DOUBLE PRECISION := 0;
    v_weighted_sum DOUBLE PRECISION := 0;
    v_key TEXT;
    v_score DOUBLE PRECISION;
    v_weight DOUBLE PRECISION;
BEGIN
    FOR v_key IN SELECT jsonb_object_keys(p_components)
    LOOP
        v_score := (p_components->>v_key)::DOUBLE PRECISION;
        v_weight := COALESCE((p_weights->>v_key)::DOUBLE PRECISION, 0);
        
        v_weighted_sum := v_weighted_sum + (v_score * v_weight);
        v_total_weight := v_total_weight + v_weight;
    END LOOP;
    
    IF v_total_weight > 0 THEN
        RETURN v_weighted_sum / v_total_weight;
    END IF;
    
    RETURN 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Determine convergence status from AI vs Our scores
CREATE OR REPLACE FUNCTION determine_convergence(
    p_our_score DOUBLE PRECISION,
    p_ai_score DOUBLE PRECISION,
    p_confidence_threshold DOUBLE PRECISION DEFAULT 0.1
) RETURNS TEXT AS $$
DECLARE
    v_diff DOUBLE PRECISION;
BEGIN
    IF p_our_score IS NULL OR p_ai_score IS NULL THEN
        RETURN 'pending';
    END IF;
    
    v_diff := ABS(p_our_score - p_ai_score);
    
    IF v_diff <= p_confidence_threshold * 10 THEN
        RETURN 'aligned';
    ELSIF v_diff <= p_confidence_threshold * 25 THEN
        RETURN 'uncertain';
    ELSE
        RETURN 'divergent';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- EDGE DETECTION FUNCTIONS
-- ============================================================================

-- Calculate expected value of a bet
CREATE OR REPLACE FUNCTION calculate_ev(
    p_win_probability DOUBLE PRECISION,
    p_decimal_odds DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
BEGIN
    RETURN (p_win_probability * (p_decimal_odds - 1)) - (1 - p_win_probability);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Detect reverse line movement
CREATE OR REPLACE FUNCTION detect_reverse_line_movement(
    p_public_percent INTEGER,
    p_line_movement DOUBLE PRECISION
) RETURNS BOOLEAN AS $$
BEGIN
    -- Public heavy on one side but line moving opposite
    RETURN (p_public_percent > 70 AND p_line_movement > 0) OR
           (p_public_percent < 30 AND p_line_movement < 0);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Calculate Kelly Criterion sizing
CREATE OR REPLACE FUNCTION kelly_criterion(
    p_win_probability DOUBLE PRECISION,
    p_decimal_odds DOUBLE PRECISION,
    p_fraction DOUBLE PRECISION DEFAULT 0.25
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_kelly DOUBLE PRECISION;
BEGIN
    -- Full Kelly: (bp - q) / b
    -- where b = odds - 1, p = win prob, q = lose prob
    v_kelly := ((p_decimal_odds - 1) * p_win_probability - (1 - p_win_probability)) / (p_decimal_odds - 1);
    
    -- Return fractional Kelly (conservative)
    RETURN GREATEST(0, LEAST(5, v_kelly * p_fraction * 100));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- ANALYTIC FUNCTIONS
-- ============================================================================

-- Calculate closing line value
CREATE OR REPLACE FUNCTION calculate_clv(
    p_opening_line DOUBLE PRECISION,
    p_closing_line DOUBLE PRECISION,
    p_result TEXT
) RETURNS DOUBLE PRECISION AS $$
BEGIN
    IF p_result = 'win' THEN
        RETURN ABS(p_opening_line - p_closing_line);
    ELSIF p_result = 'loss' THEN
        RETURN -ABS(p_opening_line - p_closing_line);
    END IF;
    RETURN 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Calculate volatility from odds history
CREATE OR REPLACE FUNCTION calculate_line_volatility(
    p_game_id TEXT,
    p_bookmaker TEXT,
    p_hours_before INTEGER DEFAULT 24
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_stddev DOUBLE PRECISION;
BEGIN
    SELECT STDDEV(spread) INTO v_stddev
    FROM odds_history
    WHERE game_id = p_game_id
      AND bookmaker = p_bookmaker
      AND time >= NOW() - (p_hours_before || ' hours')::INTERVAL;
      
    RETURN COALESCE(v_stddev, 0);
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- CONTINUOUS AGGREGATE REFRESH POLICIES
-- ============================================================================

-- Add refresh policy for hourly odds (every 1 hour)
SELECT add_continuous_aggregate_policy('odds_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Add refresh policy for daily grades (every 6 hours)
SELECT add_continuous_aggregate_policy('grades_daily',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '6 hours',
    if_not_exists => TRUE
);

-- Add refresh policy for model performance (every 12 hours)
SELECT add_continuous_aggregate_policy('model_performance_daily',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '12 hours',
    if_not_exists => TRUE
);
