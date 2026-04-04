"""
Market Scanner - Sharp Money Detection

Detects sharp money indicators through line movement analysis,
public betting percentages, and market signals.
"""
import logging
from typing import Any, Dict, List, Optional
from models import Game, MarketScanResult, SharpMoneySignal, SportType, MarketType

logger = logging.getLogger(__name__)


class MarketScanner:
    """
    Market scanner for detecting sharp money and line movement signals.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def scan(self, game: Game, side: str) -> MarketScanResult:
        """
        Scan market for sharp money signals.
        
        Args:
            game: Game data with line history
            side: "home" or "away"
            
        Returns:
            MarketScanResult with detected signals
        """
        signals = []
        
        # Check for reverse line movement
        rlm_signal = self._detect_reverse_line_movement(game, side)
        if rlm_signal.detected:
            signals.append(rlm_signal)
        
        # Check for steam moves
        steam_signal = self._detect_steam_move(game, side)
        if steam_signal.detected:
            signals.append(steam_signal)
        
        # Check for sharp/public divergence
        divergence_signal = self._detect_public_sharp_divergence(game, side)
        if divergence_signal.detected:
            signals.append(divergence_signal)
        
        # Check for early limit hits
        limit_signal = self._detect_early_limit(game, side)
        if limit_signal.detected:
            signals.append(limit_signal)
        
        # Calculate overall signal
        line_movement_score = self._calculate_line_movement_score(game, side)
        public_sharp_divergence = self._calculate_divergence(game, side)
        
        overall = sum(s.strength * s.confidence for s in signals)
        if signals:
            overall /= len(signals)
        
        return MarketScanResult(
            sharp_signals=signals,
            line_movement_score=line_movement_score,
            public_sharp_divergence=public_sharp_divergence,
            overall_signal=overall
        )
    
    def _detect_reverse_line_movement(self, game: Game, 
                                       side: str) -> SharpMoneySignal:
        """
        Detect reverse line movement (line moves against public money).
        """
        if not game.line_history or len(game.line_history) < 2:
            return SharpMoneySignal(detected=False, confidence=0.0,
                                    signal_type="rlm", strength=0.0)
        
        public_pct = game.public_betting_pct or 50
        is_home = side == "home"
        
        # Get line movement
        old_line = game.line_history[0].get("spread", 0)
        new_line = game.line_history[-1].get("spread", 0)
        
        # If public is heavy on one side but line moves other way
        if is_home:
            public_heavy = public_pct > 60
            line_toward_us = new_line < old_line  # Line moving toward home
        else:
            public_heavy = public_pct < 40
            line_toward_us = new_line > old_line  # Line moving toward away
        
        if public_heavy and line_toward_us:
            return SharpMoneySignal(
                detected=True,
                confidence=0.8,
                signal_type="reverse_line_movement",
                strength=0.7,
                details={
                    "public_pct": public_pct,
                    "old_line": old_line,
                    "new_line": new_line,
                    "side": side
                }
            )
        
        return SharpMoneySignal(detected=False, confidence=0.0,
                                signal_type="rlm", strength=0.0)
    
    def _detect_steam_move(self, game: Game, 
                           side: str) -> SharpMoneySignal:
        """Detect steam move (sudden line movement across markets)."""
        if not game.line_history:
            return SharpMoneySignal(detected=False, confidence=0.0,
                                    signal_type="steam", strength=0.0)
        
        # Look for rapid line movement in short timeframe
        recent_moves = [
            m for m in game.line_history[-5:]
            if m.get("timestamp") and 
            (game.game_time.timestamp() - m.get("timestamp", 0)) < 3600  # 1 hour
        ]
        
        if len(recent_moves) >= 2:
            spread_changes = [
                abs(m.get("spread", 0) - recent_moves[0].get("spread", 0))
                for m in recent_moves[1:]
            ]
            total_change = sum(spread_changes)
            
            if total_change >= 1.5:  # Significant move
                return SharpMoneySignal(
                    detected=True,
                    confidence=0.75,
                    signal_type="steam_move",
                    strength=min(1.0, total_change / 3),
                    details={
                        "moves": len(recent_moves),
                        "total_change": total_change
                    }
                )
        
        return SharpMoneySignal(detected=False, confidence=0.0,
                                signal_type="steam", strength=0.0)
    
    def _detect_public_sharp_divergence(self, game: Game,
                                         side: str) -> SharpMoneySignal:
        """Detect when sharp and public money are on opposite sides."""
        public_pct = game.public_betting_pct or 50
        sharp_indicator = game.sharp_money_indicator or 50
        is_home = side == "home"
        
        # Check if we're aligned with sharp against public
        if is_home:
            sharp_home = sharp_indicator > 55
            public_away = public_pct < 45
            if sharp_home and public_away:
                return SharpMoneySignal(
                    detected=True,
                    confidence=0.7,
                    signal_type="sharp_alignment",
                    strength=0.6,
                    details={
                        "public_pct": public_pct,
                        "sharp_indicator": sharp_indicator
                    }
                )
        else:
            sharp_away = sharp_indicator < 45
            public_home = public_pct > 55
            if sharp_away and public_home:
                return SharpMoneySignal(
                    detected=True,
                    confidence=0.7,
                    signal_type="sharp_alignment",
                    strength=0.6,
                    details={
                        "public_pct": public_pct,
                        "sharp_indicator": sharp_indicator
                    }
                )
        
        return SharpMoneySignal(detected=False, confidence=0.0,
                                signal_type="divergence", strength=0.0)
    
    def _detect_early_limit(self, game: Game, 
                            side: str) -> SharpMoneySignal:
        """Detect early limit hits at sharp books."""
        limits = getattr(game, "early_limits", [])
        if not limits:
            return SharpMoneySignal(detected=False, confidence=0.0,
                                    signal_type="limit", strength=0.0)
        
        for limit in limits:
            if limit.get("side") == side and limit.get("hit_early", False):
                return SharpMoneySignal(
                    detected=True,
                    confidence=0.85,
                    signal_type="early_limit",
                    strength=0.8,
                    details={"book": limit.get("book", "unknown")}
                )
        
        return SharpMoneySignal(detected=False, confidence=0.0,
                                signal_type="limit", strength=0.0)
    
    def _calculate_line_movement_score(self, game: Game, 
                                       side: str) -> float:
        """Calculate score based on line movement favor."""
        if not game.line_history or len(game.line_history) < 2:
            return 0.0
        
        is_home = side == "home"
        opening = game.line_history[0].get("spread", 0)
        current = game.line_history[-1].get("spread", 0)
        
        movement = current - opening
        
        if is_home:
            # Negative movement favors home (line getting smaller)
            return -movement * 0.5
        else:
            # Positive movement favors away (line getting larger)
            return movement * 0.5
    
    def _calculate_divergence(self, game: Game, side: str) -> float:
        """Calculate sharp/public divergence score."""
        public_pct = game.public_betting_pct or 50
        sharp_indicator = game.sharp_money_indicator or 50
        is_home = side == "home"
        
        if is_home:
            # Positive if sharp likes home more than public
            return (sharp_indicator - public_pct) / 50
        else:
            # Positive if sharp likes away more than public
            return (public_pct - sharp_indicator) / 50
