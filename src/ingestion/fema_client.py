import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# Flood zone → risk score mapping based on FEMA zone severity
ZONE_RISK_MAP = {
    "V":  95,  # Coastal high hazard area
    "VE": 95,
    "A":  80,  # 100-year floodplain
    "AE": 80,
    "AH": 75,
    "AO": 75,
    "AR": 70,
    "A99": 65,
    "D":  40,  # Undetermined risk
    "X":  15,  # Minimal flood hazard (formerly Zone C)
    "B":  25,  # Moderate flood hazard (formerly Zone B)
    "C":  10,  # Minimal flood hazard
}

# NRI Risk Rating → approximate FEMA flood zone mapping
# The NRI uses a 0-100 score; we map it to a representative flood zone
# and a corresponding SFHA flag for downstream scoring.
NRI_SCORE_TO_ZONE = [
    # (min_percentile, flood_zone, is_sfha, description)
    (75, "AE",  True,  "High loss rate → 100-year floodplain equivalent"),
    (55, "AO",  True,  "Moderate-high  → shallow/recurring flooding"),
    (35, "B",   False, "Moderate       → some flood hazard"),
    (15, "X",   False, "Low            → minimal flood hazard"),
    (0,  "C",   False, "Very low       → negligible flood hazard"),
]


class FemaClient:
    """
    Client for the FEMA National Flood Hazard Layer (NFHL) ArcGIS REST API.

    Queries Layer 28 (Flood Hazard Zones) of the public NFHL MapServer
    to retrieve flood zone classification, SFHA status, and static base
    flood elevation for a given coordinate.

    When the NFHL endpoint is unreachable (e.g. geo-blocked from non-US
    IPs), falls back to a two-step approach:
      1. Census Bureau geocoder: lat/lon → county FIPS code
      2. FEMA NRI ArcGIS Online: county FIPS → flood risk scores

    Both fallback APIs are globally accessible (no geo-blocking).

    Docs: https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer
    """

    QUERY_URL = (
        "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"
    )

    CENSUS_GEOCODER_URL = (
        "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    )

    # FEMA National Risk Index — county-level data hosted on ArcGIS Online
    # (accessible worldwide, unlike hazards.fema.gov)
    NRI_COUNTIES_URL = (
        "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/"
        "National_Risk_Index_Counties/FeatureServer/0/query"
    )

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "ClimateNexus-Hackathon/1.0 (climatenexus@jll.com)"}
        )

    async def get_flood_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Query the FEMA NFHL for the flood zone containing (lat, lon).

        Returns a dict with:
            flood_risk_score   – int 0-100 derived from the FEMA zone
            flood_zone         – str  e.g. "AE", "X", "VE"
            is_sfha            – bool whether the point is in a Special Flood Hazard Area
            base_flood_elevation – float|None  static BFE in feet (if available)
        """
        params = {
            "where": "1=1",
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelWithin",
            "outFields": "FLD_ZONE,SFHA_TF,STATIC_BFE",
            "returnGeometry": "false",
            "f": "json",
        }

        try:
            resp = await self.client.get(self.QUERY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            features = data.get("features", [])
            if not features:
                logger.info("FEMA: No flood zone feature found for (%s, %s)", lat, lon)
                return {
                    "flood_risk_score": 10,
                    "flood_zone": "X",
                    "is_sfha": False,
                    "base_flood_elevation": None,
                }

            attrs = features[0]["attributes"]
            zone = (attrs.get("FLD_ZONE") or "X").strip()
            sfha_tf = (attrs.get("SFHA_TF") or "F").strip().upper()
            is_sfha = sfha_tf == "T"
            bfe = attrs.get("STATIC_BFE")
            # FEMA uses -9999 or -8888 as "no data" sentinel values
            if bfe is not None and bfe < 0:
                bfe = None

            risk_score = ZONE_RISK_MAP.get(zone, 30)

            return {
                "flood_risk_score": risk_score,
                "flood_zone": zone,
                "is_sfha": is_sfha,
                "base_flood_elevation": bfe,
            }

        except httpx.HTTPStatusError as exc:
            logger.error("FEMA API HTTP error: %s", exc)
        except httpx.RequestError as exc:
            logger.error("FEMA API request error (likely geo-blocked): %s", exc)
        except (KeyError, ValueError) as exc:
            logger.error("FEMA API parse error: %s", exc)

        # ---- Tier 2: Live NRI lookup via Census geocoder + ArcGIS Online ----
        logger.info(
            "NFHL API unreachable — falling back to NRI county lookup for (%s, %s)",
            lat, lon,
        )
        return await self._nri_county_fallback(lat, lon)

    # ------------------------------------------------------------------
    # Tier-2 fallback: Census geocoder → NRI ArcGIS Online
    # ------------------------------------------------------------------

    async def _nri_county_fallback(
        self, lat: float, lon: float,
    ) -> Dict[str, Any]:
        """
        Fall back to the FEMA National Risk Index (county-level).

        Steps:
          1. Census Bureau geocoder: (lat, lon) → 5-digit county FIPS
          2. FEMA NRI on ArcGIS Online: county FIPS → flood risk scores

        Both services are globally accessible (no geo-blocking).
        """
        county_fips = await self._get_county_fips(lat, lon)
        if not county_fips:
            return self._static_fallback()

        nri_result = await self._query_nri(county_fips)
        if nri_result:
            return nri_result

        return self._static_fallback()

    async def _get_county_fips(
        self, lat: float, lon: float,
    ) -> Optional[str]:
        """
        Query the Census Bureau geocoder to get the 5-digit county FIPS
        code for a given (lat, lon).  Accessible worldwide.
        """
        params = {
            "x": str(lon),
            "y": str(lat),
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }

        try:
            resp = await self.client.get(
                self.CENSUS_GEOCODER_URL, params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            counties = (
                data.get("result", {})
                .get("geographies", {})
                .get("Counties", [])
            )
            if counties:
                state_fips = counties[0].get("STATE", "")
                county_code = counties[0].get("COUNTY", "")
                fips = f"{state_fips}{county_code}"
                logger.info(
                    "Census geocoder: (%s, %s) → county FIPS %s (%s, %s)",
                    lat, lon, fips,
                    counties[0].get("NAME", ""),
                    state_fips,
                )
                return fips

            logger.warning(
                "Census geocoder returned no county for (%s, %s)", lat, lon,
            )
            return None

        except Exception as exc:
            logger.error("Census geocoder error: %s", exc)
            return None

    async def _query_nri(
        self, county_fips: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Query the FEMA National Risk Index (county level) on ArcGIS Online.

        Uses the inland flooding (IFLD) and coastal flooding (CFLD)
        risk scores to derive a composite flood risk score.
        """
        params = {
            "where": f"STCOFIPS='{county_fips}'",
            "outFields": (
                "STCOFIPS,COUNTY,STATE,"
                "IFLD_ALR_NPCTL,IFLD_HLRR,"
                "CFLD_ALR_NPCTL"
            ),
            "returnGeometry": "false",
            "f": "json",
        }

        try:
            resp = await self.client.get(self.NRI_COUNTIES_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            features = data.get("features", [])
            if not features:
                logger.warning(
                    "NRI: No data found for county FIPS %s", county_fips,
                )
                return None

            attrs = features[0]["attributes"]
            # Use loss RATE percentiles (normalized by exposure), not
            # absolute risk scores — absolute scores are biased by county
            # size/population (e.g. Maricopa = "Very High" just because
            # it's huge, even though per-property flood probability is low).
            inland_rate = attrs.get("IFLD_ALR_NPCTL") or 0
            coastal_rate = attrs.get("CFLD_ALR_NPCTL") or 0
            hlr_rating = attrs.get("IFLD_HLRR") or ""
            county_name = attrs.get("COUNTY", "Unknown")
            state_name = attrs.get("STATE", "Unknown")

            # Composite: take the higher of inland/coastal loss rate
            loss_rate_pctl = max(inland_rate, coastal_rate)

            # Map loss rate percentile to flood zone and risk score
            flood_zone = "X"
            is_sfha = False
            for threshold, zone, sfha, _desc in NRI_SCORE_TO_ZONE:
                if loss_rate_pctl >= threshold:
                    flood_zone = zone
                    is_sfha = sfha
                    break

            risk_score = self._nri_to_risk_score(loss_rate_pctl, flood_zone)

            logger.info(
                "NRI fallback: %s County, %s → flood_risk_score=%d, zone=%s "
                "(inland_rate=%.1f%%, coastal_rate=%.1f%%, HLR=%s)",
                county_name, state_name, risk_score, flood_zone,
                inland_rate, coastal_rate, hlr_rating,
            )

            return {
                "flood_risk_score": risk_score,
                "flood_zone": flood_zone,
                "is_sfha": is_sfha,
                "base_flood_elevation": None,
            }

        except Exception as exc:
            logger.error("NRI ArcGIS query error: %s", exc)
            return None

    @staticmethod
    def _nri_to_risk_score(nri_score: float, flood_zone: str) -> int:
        """
        Convert an NRI percentile score (0-100) to a risk score (0-100)
        aligned with the FEMA zone-based scoring system.

        NRI scores are national percentiles — a score of 95 means the
        county is in the 95th percentile for flood risk nationally.
        We use the mapped flood zone as an anchor and blend it with
        the NRI percentile.
        """
        zone_base = ZONE_RISK_MAP.get(flood_zone, 30)
        # Weighted blend: 30% zone-based anchor, 70% NRI loss rate
        # percentile (rate-based metric better reflects per-property risk)
        blended = 0.3 * zone_base + 0.7 * nri_score
        return int(min(100, max(0, blended)))

    @staticmethod
    def _static_fallback() -> Dict[str, Any]:
        """Last-resort fallback when both NFHL and NRI are unreachable."""
        return {
            "flood_risk_score": 30,
            "flood_zone": "D",
            "is_sfha": False,
            "base_flood_elevation": None,
        }

    async def close(self):
        await self.client.aclose()
