import httpx

from core.geocode import resolve
from .base import BaseModule, ModuleContext

# SoilGrids properties we care about for crop health
_PROPERTIES = ["phh2o", "nitrogen", "ocd", "clay", "sand"]
_DEPTH      = "0-30cm"


class SoilModule(BaseModule):
    """
    Fetches soil properties from SoilGrids (ISRIC) — free, no API key,
    250 m resolution, global coverage including India.
    """
    name = "soil"

    async def get_context(self, crop: str, location: str, date: str) -> ModuleContext:
        if not location:
            return ModuleContext(
                module_name=self.name, available=False,
                summary="Soil: no location provided",
            )

        coords = await resolve(location)
        if not coords:
            return ModuleContext(
                module_name=self.name, available=False,
                summary=f"Soil: could not resolve '{location}'",
            )

        lat, lon, name = coords
        try:
            params = {
                "lon":      lon,
                "lat":      lat,
                "property": _PROPERTIES,
                "depth":    _DEPTH,
                "value":    "mean",
            }
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(
                    "https://rest.isric.org/soilgrids/v2.0/properties/query",
                    params=params,
                )
                r.raise_for_status()
                data = r.json()
            return self._build_context(data, name)
        except Exception as e:
            return ModuleContext(
                module_name=self.name, available=False,
                summary=f"Soil: unavailable ({e})",
            )

    def _build_context(self, data: dict, name: str) -> ModuleContext:
        props  = data.get("properties", {}).get("layers", [])
        detail: dict[str, float] = {}

        for layer in props:
            prop_name = layer.get("name", "")
            depths    = layer.get("depths", [])
            for d in depths:
                if d.get("label") == _DEPTH:
                    val = d.get("values", {}).get("mean")
                    if val is not None:
                        # SoilGrids stores values ×10 for pH, ×100 for others
                        if prop_name == "phh2o":
                            detail["ph"] = round(val / 10, 1)
                        elif prop_name == "nitrogen":
                            detail["nitrogen_g_kg"] = round(val / 100, 2)
                        elif prop_name == "ocd":
                            detail["organic_carbon_g_kg"] = round(val / 10, 2)
                        elif prop_name == "clay":
                            detail["clay_pct"] = round(val / 10, 1)
                        elif prop_name == "sand":
                            detail["sand_pct"] = round(val / 10, 1)

        if not detail:
            return ModuleContext(
                module_name=self.name, available=False,
                summary="Soil: no data returned for this location",
            )

        ph  = detail.get("ph", "?")
        n   = detail.get("nitrogen_g_kg", "?")
        oc  = detail.get("organic_carbon_g_kg", "?")

        summary = (
            f"Soil at {name} (0–30 cm): pH {ph}, "
            f"nitrogen {n} g/kg, organic carbon {oc} g/kg"
        )
        if "clay_pct" in detail:
            summary += f", clay {detail['clay_pct']}%"

        return ModuleContext(
            module_name=self.name,
            available=True,
            summary=summary,
            detail=detail,
        )
