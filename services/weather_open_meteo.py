"""
Open-Meteo weather helper.

Free, no API key. Used for outdoor sports (NFL, NCAAF) where the StatsAPI
weather feed MLB enjoys doesn't exist. Returns the same dict shape MLB
already produces so the grade engine reads it uniformly:

    {"condition": str, "temp": int, "wind": str}

If anything goes wrong (no coords, network fail, parse error) returns {}
so callers can treat it the same as "weather unavailable".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger("edge-crew-v3.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def _wmo_to_condition(code: Optional[int]) -> str:
    """Map WMO weather codes to short labels."""
    if code is None:
        return ""
    if code == 0:
        return "Clear"
    if code in (1, 2, 3):
        return "Partly cloudy"
    if code in (45, 48):
        return "Fog"
    if 51 <= code <= 67:
        return "Rain"
    if 71 <= code <= 77:
        return "Snow"
    if 80 <= code <= 82:
        return "Showers"
    if 85 <= code <= 86:
        return "Snow showers"
    if 95 <= code <= 99:
        return "Thunderstorm"
    return "Unknown"


async def fetch_weather(
    lat: float,
    lon: float,
    when_iso: Optional[str] = None,
    timeout: float = 10.0,
) -> dict:
    """Fetch weather for the hour closest to `when_iso` (UTC ISO string).
    Returns {} on any failure."""
    if httpx is None:
        return {}
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,precipitation,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 2,
            "timezone": "UTC",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(OPEN_METEO_URL, params=params)
        if r.status_code != 200:
            logger.debug(f"open-meteo HTTP {r.status_code}")
            return {}
        data = r.json()
        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            return {}

        # Find the hour bucket closest to when_iso
        target_idx = 0
        if when_iso:
            try:
                target = datetime.fromisoformat(when_iso.replace("Z", "+00:00"))
                # open-meteo returns naive iso strings — treat as UTC
                best_dt = None
                for i, t in enumerate(times):
                    try:
                        dt = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
                    except Exception:
                        continue
                    if best_dt is None or abs((dt - target).total_seconds()) < abs((best_dt - target).total_seconds()):
                        best_dt = dt
                        target_idx = i
            except Exception:
                target_idx = 0

        def _pick(key: str):
            arr = hourly.get(key) or []
            return arr[target_idx] if target_idx < len(arr) else None

        temp = _pick("temperature_2m")
        wind_mph = _pick("wind_speed_10m")
        wind_dir = _pick("wind_direction_10m")
        code = _pick("weather_code")

        out: dict = {}
        if temp is not None:
            try:
                out["temp"] = int(round(float(temp)))
            except Exception:
                pass
        if wind_mph is not None:
            try:
                if wind_dir is not None:
                    out["wind"] = f"{int(round(float(wind_mph)))} mph @ {int(round(float(wind_dir)))}\u00b0"
                else:
                    out["wind"] = f"{int(round(float(wind_mph)))} mph"
            except Exception:
                pass
        cond = _wmo_to_condition(int(code) if code is not None else None)
        if cond:
            out["condition"] = cond
        return out
    except Exception as e:
        logger.debug(f"open-meteo fetch failed: {e}")
        return {}
