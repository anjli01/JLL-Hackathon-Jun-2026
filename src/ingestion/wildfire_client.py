import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class WildfireClient:
    """
    Client for the USDA Forest Service Wildfire Risk to Communities data.

    Queries the ArcGIS ImageServer for burn probability at a given coordinate
    using the `identify` operation on the published raster service.

    Endpoint docs:
      https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/
      USFS_EDW_RMRS_WRC_BurnProbability/ImageServer
    """

    IDENTIFY_URL = (
        "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/"
        "USFS_EDW_RMRS_WRC_BurnProbability/ImageServer/identify"
    )

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get_wildfire_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Query the USFS burn probability raster for (lat, lon).

        Returns:
            wildfire_risk_score    – int 0-100
            burn_probability       – float  raw annual burn probability
            distance_to_wui_miles  – float  estimated (derived from probability)
        """
        params = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "returnGeometry": "false",
            "returnCatalogItems": "false",
            "f": "json",
        }

        try:
            resp = await self.client.get(self.IDENTIFY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            # The identify response returns a pixel value
            raw_value = data.get("value")

            if raw_value is None or str(raw_value).strip().lower() in ("nodata", ""):
                logger.info(
                    "Wildfire: No burn probability data for (%s, %s)", lat, lon
                )
                return {
                    "wildfire_risk_score": 5,
                    "burn_probability": 0.0,
                    "distance_to_wui_miles": None,
                }

            # Raw burn probability is typically a very small float (e.g. 0.0001 – 0.05)
            burn_prob = float(raw_value)

            # Clamp and scale to 0-100
            # Burn probs above 0.02 are considered very high risk
            risk_score = int(min(100, max(0, burn_prob * 5000)))

            # Rough distance-to-WUI estimate (inverse relationship with burn prob)
            distance_wui = round(max(0.1, 10.0 / max(risk_score, 1)), 1) if risk_score > 0 else None

            return {
                "wildfire_risk_score": risk_score,
                "burn_probability": round(burn_prob, 6),
                "distance_to_wui_miles": distance_wui,
            }

        except httpx.HTTPStatusError as exc:
            logger.error("USFS Wildfire API HTTP error: %s", exc)
            return self._fallback()
        except httpx.RequestError as exc:
            logger.error("USFS Wildfire API request error: %s", exc)
            return self._fallback()
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("USFS Wildfire API parse error: %s", exc)
            return self._fallback()

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "wildfire_risk_score": 0,
            "burn_probability": 0.0,
            "distance_to_wui_miles": None,
        }

    async def close(self):
        await self.client.aclose()
