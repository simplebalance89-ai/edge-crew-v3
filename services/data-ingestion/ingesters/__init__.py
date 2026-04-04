"""
Data ingesters for various sports data providers.
"""
from ingesters.base import BaseIngester
from ingesters.odds_api import OddsAPIIngester
from ingesters.espn import ESPNIngester
from ingesters.rotowire import RotowireIngester
from ingesters.kalshi import KalshiIngester

__all__ = [
    "BaseIngester",
    "OddsAPIIngester",
    "ESPNIngester",
    "RotowireIngester",
    "KalshiIngester",
]
