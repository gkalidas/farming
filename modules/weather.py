import json
import sqlite3
from datetime import datetime, timezone

import httpx

from config import DB_PATH
from core.geocode import resolve
from .base import BaseModule, ModuleContext

_CACHE_TTL_HOURS = 6

# Open-Meteo WMO weather code → short description
_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    80: "slight showers", 81: "moderate showers", 82: "violent showers",
    95: "thunderstorm", 96: "thunderstorm + hail", 99: "thunderstorm + heavy hail",
}


class WeatherModule(BaseModule):
    name = "weather"

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        con = sqlite3.connect(DB_PATH)
        con.execute("""
            CREATE TABLE IF NOT EXISTS weather_cache (
                location   TEXT PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                data_json  TEXT NOT NULL
            )
        """)
        con.commit()
        con.close()

    def _get_cached(self, key: str) -> dict | None:
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT fetched_at, data_json FROM weather_cache WHERE location = ?", (key,)
        ).fetchone()
        con.close()
        if not row:
            return None
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(row[0])).total_seconds() / 3600
        return json.loads(row[1]) if age_h < _CACHE_TTL_HOURS else None

    def _save_cache(self, key: str, data: dict):
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT OR REPLACE INTO weather_cache VALUES (?, ?, ?)",
            (key, datetime.now(timezone.utc).isoformat(), json.dumps(data)),
        )
        con.commit()
        con.close()

    async def get_context(self, crop: str, location: str, date: str) -> ModuleContext:
        if not location:
            return ModuleContext(
                module_name=self.name, available=False,
                summary="Weather: no location provided",
                detail={"offline": True},
            )

        cached = self._get_cached(location)
        if cached:
            return self._build_context(cached)

        coords = await resolve(location)
        if not coords:
            return ModuleContext(
                module_name=self.name, available=False,
                summary=f"Weather: could not resolve '{location}'",
                detail={"offline": True},
            )

        lat, lon, name = coords
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude":  lat,
                        "longitude": lon,
                        "current":   "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
                        "forecast_days": 3,
                        "daily":     "precipitation_sum,temperature_2m_max,temperature_2m_min",
                    },
                )
                r.raise_for_status()
                data = r.json()
                data["_resolved_name"] = name
            self._save_cache(location, data)
            return self._build_context(data)
        except Exception:
            return ModuleContext(
                module_name=self.name, available=False,
                summary="Weather: network error (offline mode)",
                detail={"offline": True},
            )

    def _build_context(self, data: dict) -> ModuleContext:
        c    = data.get("current", {})
        name = data.get("_resolved_name", "unknown")
        temp = c.get("temperature_2m", "?")
        hum  = c.get("relative_humidity_2m", "?")
        rain = c.get("precipitation", 0)
        wind = c.get("wind_speed_10m", "?")
        code = c.get("weather_code", 0)
        desc = _WMO.get(code, f"code {code}")

        daily    = data.get("daily", {})
        rain_3d  = sum(daily.get("precipitation_sum", [0, 0, 0])[:3])

        summary = (
            f"Weather at {name}: {desc}, {temp}°C, humidity {hum}%, "
            f"wind {wind} km/h, rain today {rain} mm, 3-day total {rain_3d:.1f} mm"
        )

        return ModuleContext(
            module_name=self.name,
            available=True,
            summary=summary,
            detail={
                "location":    name,
                "temperature": temp,
                "humidity":    hum,
                "description": desc,
                "wind_speed":  wind,
                "rain_today":  rain,
                "rain_3d":     rain_3d,
            },
        )
