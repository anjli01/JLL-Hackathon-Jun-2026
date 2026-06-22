import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OsmClient:
    """
    Client for OpenStreetMap data via the Overpass API.

    Queries building footprints and land use information around a given
    coordinate. This context enriches the risk model by identifying building
    type, size, and surrounding land use (urban, residential, industrial, etc.).

    Endpoint: https://overpass-api.de/api/interpreter
    No API key required. Subject to rate limits.
    """

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    SEARCH_RADIUS_M = 50  # search within 50 meters of the point

    def __init__(self, timeout: float = 20.0):
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "ClimateNexus-Hackathon/1.0 (climatenexus@jll.com)"}
        )

    async def get_building_info(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Query OpenStreetMap for buildings near (lat, lon).

        Returns:
            building_type        – str|None  e.g. "commercial", "residential", "yes"
            building_levels      – int|None  number of floors
            building_found       – bool      whether a building was found at the location
            land_use             – str|None  surrounding land use tag
            nearby_buildings     – int       count of buildings within the search radius
        """
        # Overpass QL query: find buildings within SEARCH_RADIUS_M of the point
        query = f"""
        [out:json][timeout:15];
        (
          way["building"](around:{self.SEARCH_RADIUS_M},{lat},{lon});
          relation["building"](around:{self.SEARCH_RADIUS_M},{lat},{lon});
        );
        out tags;
        """

        try:
            resp = await self.client.post(
                self.OVERPASS_URL,
                data={"data": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

            elements = data.get("elements", [])

            if not elements:
                # Try to get land use even if no building found
                land_use = await self._get_land_use(lat, lon)
                return {
                    "building_type": None,
                    "building_levels": None,
                    "building_found": False,
                    "land_use": land_use,
                    "nearby_buildings": 0,
                }

            # Take the closest / first building
            first_building = elements[0]
            tags = first_building.get("tags", {})

            building_type = tags.get("building", "yes")
            levels_str = tags.get("building:levels")
            building_levels = int(levels_str) if levels_str and levels_str.isdigit() else None

            land_use = await self._get_land_use(lat, lon)

            return {
                "building_type": building_type,
                "building_levels": building_levels,
                "building_found": True,
                "land_use": land_use,
                "nearby_buildings": len(elements),
            }

        except httpx.HTTPStatusError as exc:
            logger.error("Overpass API HTTP error: %s", exc)
            return self._fallback()
        except httpx.RequestError as exc:
            logger.error("Overpass API request error: %s", exc)
            return self._fallback()
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Overpass API parse error: %s", exc)
            return self._fallback()

    async def _get_land_use(self, lat: float, lon: float) -> Optional[str]:
        """Query the dominant land use around the point."""
        query = f"""
        [out:json][timeout:10];
        (
          way["landuse"](around:200,{lat},{lon});
        );
        out tags 1;
        """
        try:
            resp = await self.client.post(
                self.OVERPASS_URL,
                data={"data": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            elements = data.get("elements", [])
            if elements:
                return elements[0].get("tags", {}).get("landuse")
        except Exception:
            pass
        return None

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "building_type": None,
            "building_levels": None,
            "building_found": False,
            "land_use": None,
            "nearby_buildings": 0,
        }

    async def close(self):
        await self.client.aclose()
