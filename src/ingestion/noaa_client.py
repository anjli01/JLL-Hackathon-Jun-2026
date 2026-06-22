import httpx
import logging
from typing import Dict, Any, List
from statistics import mean as _mean

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RCP warming projections (simplified from IPCC AR6 / US NCA5)
# ---------------------------------------------------------------------------

# Projected warming by 2050 (°F) under RCP 8.5, by absolute latitude band.
_RCP85_WARMING_BY_LAT = [
    (25, 2.5),   # Tropical / South Florida
    (30, 3.0),   # Subtropical (Gulf Coast, South TX)
    (35, 3.5),   # Warm temperate (Southeast, Mid-Atlantic)
    (40, 4.0),   # Temperate (Northeast, Midwest)
    (45, 4.5),   # Northern temperate (Great Lakes, Pacific NW)
    (90, 5.0),   # Northern (Alaska, upper Midwest)
]

# RCP 4.5 warming is approximately 60 % of RCP 8.5
_RCP45_FRACTION = 0.6


def _rcp_warming(lat: float) -> Dict[str, float]:
    """Estimate mid-century warming (°F) for both RCP scenarios."""
    abs_lat = abs(lat)
    rcp85 = 3.5  # default for mid-latitudes
    for threshold, warming in _RCP85_WARMING_BY_LAT:
        if abs_lat <= threshold:
            rcp85 = warming
            break
    return {
        "rcp45_warming_f": round(rcp85 * _RCP45_FRACTION, 1),
        "rcp85_warming_f": round(rcp85, 1),
    }


class NoaaClient:
    """
    Client for NOAA climate data via the RCC-ACIS GridData API.

    Uses gridded 30-year climate normals (nClimGrid, 1991–2020) to derive
    **stable, reproducible** heat-stress metrics based on long-term climate
    averages — not ephemeral 7-day weather forecasts.

    Supplements with simplified RCP 4.5 & RCP 8.5 warming projections to
    estimate future heat-stress exposure for risk scoring.

    Endpoint: https://data.rcc-acis.org/GridData
    No API key required.  Data source: NOAA nClimGrid (5 km resolution, CONUS).
    """

    ACIS_URL = "https://data.rcc-acis.org/GridData"

    def __init__(self, timeout: float = 25.0):
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": "ClimateNexus-Hackathon/1.0 (climatenexus@jll.com)",
                "Content-Type": "application/json",
            },
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_heat_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Derive heat-stress indicators from 30-year climate normals.

        Queries the RCC-ACIS GridData API for nClimGrid annual summaries
        (1991–2020), then computes:
          • Average annual maximum temperature (°F)
          • Average number of extreme-heat days (daily max ≥ 95 °F) per year
          • Estimated annual cooling degree days (CDD, base 65 °F)
          • RCP 4.5 & 8.5 projected warming and future extreme-heat days

        Returns a dict with at least:
            heat_risk_score              – int 0-100
            projected_extreme_heat_days  – int  avg annual days ≥ 95 °F (RCP 8.5)
            cooling_degree_days          – int  estimated annual CDD (base 65 °F)
        """
        # ACIS expects lon,lat (note order!)
        payload = {
            "loc": f"{lon},{lat}",
            "grid": "21",
            "sDate": "1991",
            "eDate": "2020",
            "elems": [
                # Col 1: annual avg of daily max temps
                {
                    "name": "maxt",
                    "interval": "yly",
                    "duration": "yly",
                    "reduce": "mean",
                },
                # Col 2: annual avg of daily mean temps
                {
                    "name": "avgt",
                    "interval": "yly",
                    "duration": "yly",
                    "reduce": "mean",
                },
            ],
        }

        try:
            resp = await self.client.post(self.ACIS_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            rows = data.get("data", [])
            if not rows:
                logger.warning(
                    "ACIS GridData: no data returned for (%s, %s)", lat, lon
                )
                return self._fallback()

            return self._parse_acis_response(rows, lat)

        except httpx.HTTPStatusError as exc:
            logger.error("ACIS HTTP error: %s", exc)
            return self._fallback()
        except httpx.RequestError as exc:
            logger.error("ACIS request error: %s", exc)
            return self._fallback()
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("ACIS parse error: %s", exc)
            return self._fallback()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_acis_response(
        self, rows: List, lat: float
    ) -> Dict[str, Any]:
        """Parse ACIS annual rows into heat-risk metrics."""
        annual_max_temps: List[float] = []
        annual_avg_temps: List[float] = []
        annual_extreme_days: List[float] = []

        _missing = {"M", "-999", ""}

        for row in rows:
            # row = ["YYYY", maxt_mean, avgt_mean]
            # Values are strings; "M" means missing.
            vals = row[1:]  # skip year label

            if len(vals) >= 1 and str(vals[0]).strip() not in _missing:
                maxt = float(vals[0])
                annual_max_temps.append(maxt)
                # Estimate extreme heat days (>= 95F) based on average max temp
                # If avg max temp is 85F+, it means summer is hot.
                extreme_days = max(0, (maxt - 75) * 5)
                annual_extreme_days.append(extreme_days)
            if len(vals) >= 2 and str(vals[1]).strip() not in _missing:
                annual_avg_temps.append(float(vals[1]))

        if not annual_max_temps or not annual_avg_temps:
            logger.warning("ACIS: all temperature data missing")
            return self._fallback()

        # ---- 30-year climate normals ----
        avg_max_temp = _mean(annual_max_temps)
        avg_temp = _mean(annual_avg_temps)
        avg_extreme_heat_days = (
            _mean(annual_extreme_days) if annual_extreme_days else 0.0
        )

        # ---- Estimated annual CDD (base 65 °F) ----
        # CDD = Σ max(0, T_daily − 65) across the year.
        # Approximate from annual averages using a degree-day model:
        #   warm-season contribution ≈ (avg_daily_mean − 50) × 15
        #   peak-season contribution ≈ (avg_daily_max  − 65) × 120
        cdd_estimate = int(
            max(0, (avg_temp - 50) * 15 + (avg_max_temp - 65) * 120)
        )

        # ---- RCP warming projections ----
        warming = _rcp_warming(lat)

        # Projected extreme-heat days under RCP 8.5 (mid-century)
        # Each 1 °F of warming adds ~3–8 extreme-heat days, depending on
        # the current baseline (hotter baselines amplify more).
        added_days = warming["rcp85_warming_f"] * max(
            3.0, avg_extreme_heat_days * 0.30
        )
        rcp85_extreme_days = avg_extreme_heat_days + added_days

        # ---- Composite heat-risk score (0–100) ----
        # Blends current climate severity with RCP 8.5 future projections.
        raw_score = (
            (avg_max_temp - 60) * 1.0           # baseline warmth
            + avg_extreme_heat_days * 2.0        # current extreme days
            + rcp85_extreme_days * 1.5           # projected future extreme days
            + max(0, cdd_estimate - 500) * 0.02  # high-CDD penalty
        )
        score = int(min(100, max(0, raw_score)))

        return {
            "heat_risk_score": score,
            "projected_extreme_heat_days": int(round(rcp85_extreme_days)),
            "cooling_degree_days": cdd_estimate,
            "avg_annual_max_temp_f": round(avg_max_temp, 1),
            "rcp45_warming_f": warming["rcp45_warming_f"],
            "rcp85_warming_f": warming["rcp85_warming_f"],
            "climate_normal_period": "1991-2020",
        }

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "heat_risk_score": 0,
            "projected_extreme_heat_days": 0,
            "cooling_degree_days": 0,
            "avg_annual_max_temp_f": None,
            "rcp45_warming_f": None,
            "rcp85_warming_f": None,
            "climate_normal_period": "1991-2020",
        }

    async def close(self):
        await self.client.aclose()
