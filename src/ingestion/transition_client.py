import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Known building performance standards mapped by (lat_range, lon_range)
# This is a rule-based lookup; a production system would scrape these portals.
REGULATIONS_DB: List[Dict[str, Any]] = [
    {
        "name": "Local Law 97 (LL97)",
        "jurisdiction": "New York City",
        "lat_range": (40.49, 40.92),
        "lon_range": (-74.26, -73.70),
        "keywords": ["new york", "nyc", "manhattan", "brooklyn", "queens", "bronx", "staten island"],
        "severity": 90,
        "description": "NYC carbon emissions caps for buildings >25,000 sq ft. Penalties start 2024.",
    },
    {
        "name": "BERDO 2.0",
        "jurisdiction": "Boston",
        "lat_range": (42.23, 42.40),
        "lon_range": (-71.19, -70.92),
        "keywords": ["boston"],
        "severity": 85,
        "description": "Boston building emissions reduction & disclosure ordinance.",
    },
    {
        "name": "Title 24 (California Building Standards)",
        "jurisdiction": "California",
        "lat_range": (32.53, 42.00),
        "lon_range": (-124.48, -114.13),
        "keywords": ["california", "los angeles", "san francisco", "san diego", "sacramento"],
        "severity": 75,
        "description": "California energy efficiency standards for residential and non-residential buildings.",
    },
    {
        "name": "Clean Energy DC Building Code (CEDC)",
        "jurisdiction": "Washington DC",
        "lat_range": (38.79, 38.99),
        "lon_range": (-77.12, -76.91),
        "keywords": ["washington", "dc", "district of columbia"],
        "severity": 80,
        "description": "DC net-zero energy requirements for new construction.",
    },
    {
        "name": "Building Performance Standard (BPS)",
        "jurisdiction": "Denver",
        "lat_range": (39.61, 39.81),
        "lon_range": (-105.11, -104.60),
        "keywords": ["denver", "colorado"],
        "severity": 70,
        "description": "Denver building performance standard for buildings >25,000 sq ft.",
    },
    {
        "name": "Building Tune-Up Ordinance",
        "jurisdiction": "Seattle",
        "lat_range": (47.49, 47.73),
        "lon_range": (-122.44, -122.24),
        "keywords": ["seattle"],
        "severity": 70,
        "description": "Seattle periodic tune-ups for commercial buildings.",
    },
]


class TransitionClient:
    """
    Client for assessing transition risk from local building performance standards.

    Uses a curated regulations database to match properties by geolocation and
    address keywords. In production, this would be supplemented by web scraping
    of local government portals via BeautifulSoup.
    """

    def __init__(self):
        self.regulations = REGULATIONS_DB

    async def get_transition_risk(
        self, lat: float, lon: float, city: str = ""
    ) -> Dict[str, Any]:
        """
        Determine transition risk based on applicable local regulations.

        Returns:
            transition_risk_score   – int 0-100
            applicable_regulations  – list of regulation names
            compliance_gap_flag     – bool  True if any high-severity regulation applies
        """
        city_lower = city.lower()
        matched_regulations: List[str] = []
        max_severity = 0

        for reg in self.regulations:
            # Match by coordinates
            lat_min, lat_max = reg["lat_range"]
            lon_min, lon_max = reg["lon_range"]
            coord_match = lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

            # Match by keywords in address
            keyword_match = any(kw in city_lower for kw in reg["keywords"])

            if coord_match or keyword_match:
                matched_regulations.append(reg["name"])
                max_severity = max(max_severity, reg["severity"])
                logger.info(
                    "Transition risk: matched '%s' (%s) for (%s, %s)",
                    reg["name"],
                    reg["jurisdiction"],
                    lat,
                    lon,
                )

        # Base risk: even without a specific regulation, there is a baseline
        risk_score = max(max_severity, 20) if matched_regulations else 20

        return {
            "transition_risk_score": risk_score,
            "applicable_regulations": matched_regulations,
            "compliance_gap_flag": risk_score > 60,
        }

    async def close(self):
        """No-op for API consistency with other clients."""
        pass
