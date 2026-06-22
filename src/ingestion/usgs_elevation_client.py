import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class UsgsElevationClient:
    """
    Client for the USGS Elevation Point Query Service (EPQS).

    Queries the 3DEP (3D Elevation Program) to retrieve terrain elevation
    for a given coordinate. Low-lying elevation is a critical input for
    flood risk modeling.

    Endpoint: https://epqs.nationalmap.gov/v1/json
    No API key required.
    """

    QUERY_URL = "https://epqs.nationalmap.gov/v1/json"

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get_elevation(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Query terrain elevation for (lat, lon).

        Returns:
            elevation_ft     – float  terrain elevation in feet
            elevation_m      – float  terrain elevation in meters
            low_lying_flag   – bool   True if elevation < 33 ft (10m) — flood proxy
        """
        params = {
            "x": str(lon),
            "y": str(lat),
            "units": "Feet",
            "output": "json",
        }

        try:
            resp = await self.client.get(self.QUERY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            # The EPQS response structure:
            # {"value": 123.45, ...} or nested under "value"
            elevation_ft = None
            if isinstance(data, dict):
                elevation_ft = data.get("value")

            if elevation_ft is None or elevation_ft == -1000000:
                logger.info("USGS Elevation: No data for (%s, %s)", lat, lon)
                return self._fallback()

            elevation_ft = float(elevation_ft)
            elevation_m = round(elevation_ft * 0.3048, 2)
            low_lying = elevation_ft < 33.0  # ~10 meters

            return {
                "elevation_ft": round(elevation_ft, 2),
                "elevation_m": elevation_m,
                "low_lying_flag": low_lying,
            }

        except httpx.HTTPStatusError as exc:
            logger.error("USGS Elevation HTTP error: %s", exc)
            return self._fallback()
        except httpx.RequestError as exc:
            logger.error("USGS Elevation request error: %s", exc)
            return self._fallback()
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("USGS Elevation parse error: %s", exc)
            return self._fallback()

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "elevation_ft": None,
            "elevation_m": None,
            "low_lying_flag": False,
        }

    async def close(self):
        await self.client.aclose()
