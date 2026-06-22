import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class UsgsSeismicClient:
    """
    Client for the USGS Seismic Design Data Web Services.

    Queries the ASCE 7-22 design ground motion parameters for a given
    coordinate. The SDS and SD1 values indicate the seismic hazard severity
    and directly inform structural risk for commercial real estate.

    Endpoint: https://earthquake.usgs.gov/ws/building-codes/asce7-22/calculate
    No API key required.
    """

    DESIGN_MAPS_URL = "https://earthquake.usgs.gov/ws/building-codes/asce7-22/calculate"

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get_seismic_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Query USGS seismic design parameters for (lat, lon).

        Uses ASCE 7-22 with Risk Category II (standard occupancy) and
        Site Class D (stiff soil, the most common default).

        Returns:
            seismic_risk_score – int 0-100
            sds                – float  Short-period design spectral acceleration
            sd1                – float  1-second design spectral acceleration
            seismic_design_category – str  e.g. "A", "B", "C", "D", "E"
            pga                – float  Peak Ground Acceleration (mapped)
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "riskCategory": "II",
            "siteClass": "D",
        }

        try:
            resp = await self.client.get(self.DESIGN_MAPS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            response_data = data.get("response", {}).get("data", {})

            sds = response_data.get("sds")
            sd1 = response_data.get("sd1")
            sdc = response_data.get("sdc", "Unknown")
            pga = response_data.get("pgam") or response_data.get("pga")

            if sds is None:
                logger.info("USGS Seismic: No design data for (%s, %s)", lat, lon)
                return self._fallback()

            sds = float(sds)
            sd1 = float(sd1) if sd1 is not None else 0.0
            pga = float(pga) if pga is not None else 0.0

            # Derive risk score from SDS (Short-period spectral acceleration)
            # SDS ranges: <0.167 (A), 0.167-0.33 (B), 0.33-0.50 (C), 0.50-1.0 (D), >1.0 (E)
            if sds < 0.167:
                risk_score = 5
            elif sds < 0.33:
                risk_score = 20
            elif sds < 0.50:
                risk_score = 40
            elif sds < 0.75:
                risk_score = 60
            elif sds < 1.0:
                risk_score = 75
            elif sds < 1.5:
                risk_score = 85
            else:
                risk_score = 95

            return {
                "seismic_risk_score": risk_score,
                "sds": round(sds, 4),
                "sd1": round(sd1, 4),
                "seismic_design_category": str(sdc),
                "pga": round(pga, 4),
            }

        except httpx.HTTPStatusError as exc:
            logger.error("USGS Seismic HTTP error: %s", exc)
            return self._fallback()
        except httpx.RequestError as exc:
            logger.error("USGS Seismic request error: %s", exc)
            return self._fallback()
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("USGS Seismic parse error: %s", exc)
            return self._fallback()

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "seismic_risk_score": 0,
            "sds": None,
            "sd1": None,
            "seismic_design_category": "Unknown",
            "pga": None,
        }

    async def close(self):
        await self.client.aclose()
