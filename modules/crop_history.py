"""
Fetches historical weather from planting date to today using
Open-Meteo archive API (ERA5 reanalysis, free, no key required).
"""

import json
import sqlite3
from datetime import date, datetime, timezone, timedelta

import httpx

from config import DB_PATH
from core.geocode import resolve
from .base import BaseModule, ModuleContext

_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


async def fetch_history(lat: float, lon: float, start: date, end: date) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(_ARCHIVE_URL, params={
            "latitude":   lat,
            "longitude":  lon,
            "start_date": start.isoformat(),
            "end_date":   end.isoformat(),
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "relative_humidity_2m_max",
                "relative_humidity_2m_min",
                "weather_code",
            ]),
            "timezone": "auto",
        })
        r.raise_for_status()
        return r.json()


def summarise(data: dict, planted_at: date) -> dict:
    daily = data.get("daily", {})
    dates     = daily.get("time", [])
    rain      = daily.get("precipitation_sum", [])
    t_max     = daily.get("temperature_2m_max", [])
    t_min     = daily.get("temperature_2m_min", [])
    hum_max   = daily.get("relative_humidity_2m_max", [])

    days_since = (date.today() - planted_at).days

    total_rain   = sum(r for r in rain if r is not None)
    avg_t_max    = sum(t for t in t_max if t is not None) / max(len(t_max), 1)
    humid_days   = sum(1 for h in hum_max if h is not None and h > 80)
    heavy_rain_days = sum(1 for r in rain if r is not None and r > 20)

    # last 7 days
    recent_rain = sum(r for r in rain[-7:] if r is not None)
    recent_humid = sum(1 for h in hum_max[-7:] if h is not None and h > 80)

    return {
        "planted_at":       planted_at.isoformat(),
        "days_since_plant": days_since,
        "total_rain_mm":    round(total_rain, 1),
        "avg_max_temp_c":   round(avg_t_max, 1),
        "humid_days_over80": humid_days,
        "heavy_rain_days":  heavy_rain_days,
        "last_7d_rain_mm":  round(recent_rain, 1),
        "last_7d_humid_days": recent_humid,
    }


class CropHistoryModule(BaseModule):
    name = "crop_history"

    def __init__(self, plot_id: int | None = None):
        self._plot_id = plot_id

    async def get_context(self, crop: str, location: str, date_str: str) -> ModuleContext:
        if not self._plot_id:
            return ModuleContext(
                module_name=self.name, available=False,
                summary="Crop history: no plot linked to this analysis",
            )

        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT planted_at, lat, lon, location, history_json FROM crop_plots WHERE id = ?",
            (self._plot_id,)
        ).fetchone()
        con.close()

        if not row:
            return ModuleContext(
                module_name=self.name, available=False,
                summary=f"Crop history: plot {self._plot_id} not found",
            )

        planted_at_str, lat, lon, plot_location, cached_json = row
        planted_at = date.fromisoformat(planted_at_str)
        today      = date.today()

        # use cached history if it's from today
        if cached_json:
            h = json.loads(cached_json)
            if h.get("_fetched_date") == today.isoformat():
                return self._build_context(h, plot_location)

        # resolve coords if not stored
        if not lat or not lon:
            coords = await resolve(plot_location or location)
            if not coords:
                return ModuleContext(
                    module_name=self.name, available=False,
                    summary=f"Crop history: could not geocode '{plot_location or location}'",
                )
            lat, lon, _ = coords

        try:
            raw  = await fetch_history(lat, lon, planted_at, today)
            summary_data = summarise(raw, planted_at)
            summary_data["_fetched_date"] = today.isoformat()

            # cache in DB
            con = sqlite3.connect(DB_PATH)
            con.execute(
                "UPDATE crop_plots SET lat = ?, lon = ?, history_json = ? WHERE id = ?",
                (lat, lon, json.dumps(summary_data), self._plot_id)
            )
            con.commit()
            con.close()

            return self._build_context(summary_data, plot_location or location)
        except Exception as e:
            return ModuleContext(
                module_name=self.name, available=False,
                summary=f"Crop history: failed to fetch weather history — {e}",
            )

    def _build_context(self, h: dict, location: str) -> ModuleContext:
        days   = h.get("days_since_plant", "?")
        rain   = h.get("total_rain_mm", "?")
        temp   = h.get("avg_max_temp_c", "?")
        humid  = h.get("humid_days_over80", "?")
        heavy  = h.get("heavy_rain_days", "?")
        r7     = h.get("last_7d_rain_mm", "?")
        h7     = h.get("last_7d_humid_days", "?")
        planted = h.get("planted_at", "?")

        summary = (
            f"Since planting ({planted}, {days} days ago) at {location}: "
            f"total rain {rain}mm, avg max temp {temp}°C, "
            f"{humid} high-humidity days (>80%), {heavy} heavy rain days (>20mm). "
            f"Last 7 days: {r7}mm rain, {h7} humid days."
        )

        return ModuleContext(
            module_name=self.name,
            available=True,
            summary=summary,
            detail=h,
        )
