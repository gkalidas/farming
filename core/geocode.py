import httpx

_cache: dict[str, tuple[float, float, str]] = {}


async def resolve(location: str) -> tuple[float, float, str] | None:
    """Return (lat, lon, canonical_name) for a location string, or None."""
    if not location:
        return None
    key = location.lower().strip()
    if key in _cache:
        return _cache[key]

    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "en"},
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if not results:
                return None
            loc = results[0]
            result = (loc["latitude"], loc["longitude"], loc.get("name", location))
            _cache[key] = result
            return result
    except Exception:
        return None
