import httpx
import logging
from typing import Dict, Any, Optional, List
from statistics import mean as _mean

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# National median EUI by property type (kBtu / sq ft)
# Source: ENERGY STAR Portfolio Manager Technical Reference (2024)
# ---------------------------------------------------------------------------
NATIONAL_MEDIAN_EUI: Dict[str, float] = {
    "office": 92.9,
    "retail": 78.1,
    "warehouse": 28.8,
    "hotel": 93.3,
    "hospital": 389.5,
    "school": 58.7,
    "multifamily": 62.0,
    "industrial": 95.0,
    "default": 80.0,
}

# ---------------------------------------------------------------------------
# ASHRAE climate-zone EUI multipliers (vs. national median)
#
# Buildings in extreme climates consume more energy.  These multipliers
# approximate the adjustment factors from CBECS & ENERGY STAR data.
# ---------------------------------------------------------------------------
_CLIMATE_ZONE_EUI_MULTIPLIER: Dict[int, float] = {
    1: 1.30,   # Very Hot-Humid  (Miami, Key West)
    2: 1.15,   # Hot-Humid       (Houston, New Orleans, South FL)
    3: 0.95,   # Warm            (Atlanta, Dallas, LA)
    4: 1.00,   # Mixed           (DC, Memphis, Nashville)
    5: 1.10,   # Cool            (Chicago, Boston, NYC)
    6: 1.20,   # Cold            (Minneapolis, Burlington)
    7: 1.35,   # Very Cold       (Duluth, International Falls)
}

# OSM / generic building type → ENERGY STAR property type
_BUILDING_TYPE_MAP: Dict[str, str] = {
    "commercial": "office",
    "office": "office",
    "retail": "retail",
    "supermarket": "retail",
    "warehouse": "warehouse",
    "hotel": "hotel",
    "hospital": "hospital",
    "school": "school",
    "university": "school",
    "apartments": "multifamily",
    "residential": "multifamily",
    "industrial": "industrial",
    "yes": "office",  # OSM default when building=yes
}


def _estimate_climate_zone(lat: float, lon: float) -> int:
    """
    Rough ASHRAE climate-zone estimate from latitude (CONUS only).

    A production system would use the official ASHRAE GIS shapefile.
    """
    abs_lat = abs(lat)
    if abs_lat < 25:
        return 1
    if abs_lat < 30:
        return 2
    if abs_lat < 33:
        return 3
    if abs_lat < 37:
        # Gulf Coast vs. interior
        return 3 if lon > -90 else 4
    if abs_lat < 40:
        return 4
    if abs_lat < 43:
        return 5
    if abs_lat < 46:
        return 6
    return 7


class EpaEnergyStarClient:
    """
    Client for EPA ENERGY STAR building energy benchmarks.

    **Primary path** – queries the public ENERGY STAR Certified Buildings
    SODA API (`data.energystar.gov`) for nearby certified buildings of the
    same property type, extracting median ENERGY STAR scores and source EUI.

    **Fallback path** – when the API is unavailable or returns no nearby
    matches, uses ASHRAE-climate-zone-adjusted national median EUI data
    (derived from CBECS / ENERGY STAR Portfolio Manager references).

    Endpoint: https://data.energystar.gov/resource/j2id-ke5k.json
    No API key required (Socrata open-data API).
    """

    # Socrata (SODA) open-data endpoint for ENERGY STAR certified buildings
    SODA_URL = "https://data.energystar.gov/resource/j2id-ke5k.json"

    # Search radius in meters for the SODA within_circle query
    SEARCH_RADIUS_M = 80_000  # 80 km ≈ 50 mi

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": "ClimateNexus-Hackathon/1.0 (climatenexus@jll.com)",
            },
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_energy_benchmark(
        self, lat: float, lon: float, building_type: str = "office"
    ) -> Dict[str, Any]:
        """
        Get energy benchmarking data for a building type at a location.

        Returns:
            energy_star_score_benchmark – int      median score from nearby
                                                    certified buildings (or 50)
            national_median_eui         – float    national median EUI (kBtu/sq ft)
            climate_adjusted_eui        – float    EUI adjusted for climate zone
            climate_zone                – int      estimated ASHRAE climate zone
            building_type_used          – str      ENERGY STAR property type used
            energy_risk_flag            – bool     True if adjusted EUI > 100
            data_source                 – str      "energy_star_soda_api" | "climate_zone_benchmark"
        """
        es_type = _BUILDING_TYPE_MAP.get(
            (building_type or "office").lower(), "default"
        )
        climate_zone = _estimate_climate_zone(lat, lon)

        # --- Try the ENERGY STAR Certified Buildings API first ---
        api_result = await self._try_soda_api(lat, lon, es_type)
        if api_result is not None:
            # Enrich with climate zone info
            api_result["climate_zone"] = climate_zone
            api_result["building_type_used"] = es_type
            api_result["data_source"] = "energy_star_soda_api"
            return api_result

        # --- Fallback: climate-zone-adjusted national median ---
        return self._climate_zone_benchmark(es_type, climate_zone)

    # ------------------------------------------------------------------
    # SODA API query
    # ------------------------------------------------------------------

    async def _try_soda_api(
        self, lat: float, lon: float, es_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Query the ENERGY STAR Certified Buildings SODA API for nearby
        buildings of the same property type and extract median metrics.
        """
        try:
            params = {
                "$where": (
                    f"within_circle(geocoded_column, {lat}, {lon}, "
                    f"{self.SEARCH_RADIUS_M})"
                ),
                "$limit": "30",
            }

            resp = await self.client.get(self.SODA_URL, params=params)
            resp.raise_for_status()
            buildings: List[Dict] = resp.json()

            if not buildings:
                logger.info(
                    "ENERGY STAR SODA: no certified buildings within "
                    "%d m of (%s, %s)",
                    self.SEARCH_RADIUS_M,
                    lat,
                    lon,
                )
                return None

            # Extract scores and EUI values (field names may vary)
            scores: List[float] = []
            euis: List[float] = []
            for b in buildings:
                for score_key in ("energy_star_score", "score", "year_ending_energy_star_score"):
                    val = b.get(score_key)
                    if val is not None:
                        try:
                            scores.append(float(val))
                        except (ValueError, TypeError):
                            pass
                        break
                for eui_key in ("source_eui", "site_eui", "weather_normalized_source_eui"):
                    val = b.get(eui_key)
                    if val is not None:
                        try:
                            euis.append(float(val))
                        except (ValueError, TypeError):
                            pass
                        break

            benchmark_score = int(_mean(scores)) if scores else 50
            base_eui = NATIONAL_MEDIAN_EUI.get(es_type, NATIONAL_MEDIAN_EUI["default"])
            median_eui = round(_mean(euis), 1) if euis else base_eui

            logger.info(
                "ENERGY STAR SODA: found %d buildings near (%s, %s); "
                "median score=%d, median EUI=%.1f",
                len(buildings),
                lat,
                lon,
                benchmark_score,
                median_eui,
            )

            return {
                "energy_star_score_benchmark": benchmark_score,
                "national_median_eui": base_eui,
                "climate_adjusted_eui": median_eui,  # from real data
                "energy_risk_flag": median_eui > 100.0,
                "soda_sample_size": len(buildings),
            }

        except httpx.HTTPStatusError as exc:
            logger.debug("ENERGY STAR SODA HTTP error (falling back): %s", exc)
        except httpx.RequestError as exc:
            logger.debug("ENERGY STAR SODA request error (falling back): %s", exc)
        except Exception as exc:
            logger.debug("ENERGY STAR SODA unexpected error: %s", exc)

        return None

    # ------------------------------------------------------------------
    # Climate-zone fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _climate_zone_benchmark(
        es_type: str, climate_zone: int
    ) -> Dict[str, Any]:
        """
        Produce location-aware EUI benchmarks using ASHRAE climate-zone
        adjustments to the national median.
        """
        base_eui = NATIONAL_MEDIAN_EUI.get(es_type, NATIONAL_MEDIAN_EUI["default"])
        multiplier = _CLIMATE_ZONE_EUI_MULTIPLIER.get(climate_zone, 1.0)
        adjusted_eui = round(base_eui * multiplier, 1)

        return {
            "energy_star_score_benchmark": 50,  # national median by definition
            "national_median_eui": base_eui,
            "climate_adjusted_eui": adjusted_eui,
            "climate_zone": climate_zone,
            "building_type_used": es_type,
            "energy_risk_flag": adjusted_eui > 100.0,
            "data_source": "climate_zone_benchmark",
        }

    async def close(self):
        await self.client.aclose()
