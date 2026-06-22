"""
Incentive Finder — matches property location to available tax credits,
rebates, and financing programs.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Curated incentive database
# ---------------------------------------------------------------------------

INCENTIVES_DB = [
    # Federal (IRA)
    {
        "id": "ira_179d",
        "name": "IRA Section 179D — Commercial Building Energy Efficiency Deduction",
        "type": "tax_deduction",
        "level": "federal",
        "states": None,  # All states
        "value": "$0.50–$5.00 per sq ft (up to $5/sq ft with prevailing wage)",
        "value_per_sqft": 5.0,
        "eligible_measures": ["led_lighting", "heat_pump_ashp", "bms_upgrade", "building_envelope", "cool_roof"],
        "description": "Tax deduction for commercial buildings achieving ≥25% energy savings vs ASHRAE 90.1-2007.",
    },
    {
        "id": "ira_48_solar",
        "name": "IRA Section 48 — Investment Tax Credit (Solar PV)",
        "type": "tax_credit",
        "level": "federal",
        "states": None,
        "value": "30% of installed cost (through 2032)",
        "value_pct": 0.30,
        "eligible_measures": ["solar_pv"],
        "description": "30% investment tax credit for commercial solar installations.",
    },
    {
        "id": "ira_48_geothermal",
        "name": "IRA Section 48 — Investment Tax Credit (Geothermal)",
        "type": "tax_credit",
        "level": "federal",
        "states": None,
        "value": "30% of installed cost",
        "value_pct": 0.30,
        "eligible_measures": ["heat_pump_ashp"],
        "description": "30% ITC for geothermal heat pump systems.",
    },
    # State-level
    {
        "id": "ny_sun",
        "name": "NY-Sun Commercial Solar Incentive",
        "type": "rebate",
        "level": "state",
        "states": ["NY", "New York"],
        "value": "Up to $0.20/watt for commercial solar",
        "value_per_watt": 0.20,
        "eligible_measures": ["solar_pv"],
        "description": "New York State solar incentive program for commercial installations.",
    },
    {
        "id": "nyc_accelerator",
        "name": "NYC Accelerator — Free Decarbonization Advisory",
        "type": "technical_assistance",
        "level": "local",
        "states": ["NY", "New York"],
        "value": "Free energy audits, project management, and incentive navigation",
        "eligible_measures": ["heat_pump_ashp", "bms_upgrade", "building_envelope", "led_lighting"],
        "description": "Free advisory program for NYC buildings pursuing LL97 compliance.",
    },
    {
        "id": "masssave",
        "name": "MassSave — Commercial Energy Efficiency",
        "type": "rebate",
        "level": "state",
        "states": ["MA", "Massachusetts", "Boston"],
        "value": "Up to $10,000 per heat pump system; 75–100% insulation coverage",
        "eligible_measures": ["heat_pump_ashp", "led_lighting", "building_envelope", "bms_upgrade"],
        "description": "Massachusetts utility-funded efficiency program with generous rebates.",
    },
    {
        "id": "cpace",
        "name": "C-PACE Financing",
        "type": "financing",
        "level": "state",
        "states": None,  # Available in 37+ states
        "value": "100% project financing, 15–25 year term, non-recourse",
        "eligible_measures": ["solar_pv", "heat_pump_ashp", "bms_upgrade", "building_envelope",
                              "cool_roof", "led_lighting", "flood_barriers", "elevated_mechanicals"],
        "description": "Property-assessed clean energy financing — stays with the building, not the owner.",
    },
    {
        "id": "fema_hmgp",
        "name": "FEMA Hazard Mitigation Grant Program (HMGP)",
        "type": "grant",
        "level": "federal",
        "states": None,
        "value": "75% federal cost share, up to $3M per project",
        "value_pct": 0.75,
        "eligible_measures": ["flood_barriers", "elevated_mechanicals"],
        "description": "Federal grant for flood mitigation after disaster declarations.",
    },
    {
        "id": "fema_bric",
        "name": "FEMA BRIC — Pre-Disaster Mitigation Grant",
        "type": "grant",
        "level": "federal",
        "states": None,
        "value": "75% federal cost share, up to $50M per project",
        "value_pct": 0.75,
        "eligible_measures": ["flood_barriers", "elevated_mechanicals", "ember_resistant_roof"],
        "description": "Annual competitive grant for pre-disaster resilience projects.",
    },
    {
        "id": "ca_sgip",
        "name": "California SGIP — Self-Generation Incentive Program",
        "type": "rebate",
        "level": "state",
        "states": ["CA", "California"],
        "value": "Up to $1.00/Wh for energy storage",
        "eligible_measures": ["solar_pv"],
        "description": "California incentive for energy storage paired with solar.",
    },
]


class IncentiveFinder:
    """Matches property location and planned measures to available incentives."""

    def __init__(self):
        self.incentives = INCENTIVES_DB

    def find_incentives(
        self,
        state: str = "",
        city: str = "",
        measures: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Find applicable incentives for a given location and set of measures.

        Args:
            state:    State name or abbreviation (e.g., "NY", "California")
            city:     City name (e.g., "New York", "Boston")
            measures: List of measure IDs to match against

        Returns list of matching incentive dicts.
        """
        location_str = f"{city} {state}".strip().lower()
        matched: list[dict] = []

        for incentive in self.incentives:
            # Check location eligibility
            if incentive["states"] is not None:
                location_match = any(
                    s.lower() in location_str
                    for s in incentive["states"]
                )
                if not location_match:
                    continue

            # Check measure eligibility
            if measures:
                measure_match = any(
                    m in incentive["eligible_measures"]
                    for m in measures
                )
                if not measure_match:
                    continue

            matched.append({
                "id": incentive["id"],
                "name": incentive["name"],
                "type": incentive["type"],
                "level": incentive["level"],
                "value": incentive["value"],
                "description": incentive["description"],
            })

        return matched

    def estimate_total_incentive_value(
        self,
        incentives: list[dict],
        total_project_cost: float,
        building_sqft: int = 50000,
    ) -> float:
        """Rough estimate of total incentive value in USD."""
        total = 0.0
        for inc in incentives:
            # Look up the full incentive record
            full = next((i for i in self.incentives if i["id"] == inc["id"]), None)
            if not full:
                continue

            if "value_per_sqft" in full:
                total += full["value_per_sqft"] * building_sqft
            elif "value_pct" in full:
                total += full["value_pct"] * total_project_cost
            elif "value_per_watt" in full:
                # Rough: assume 10W per sq ft of roof = ~50% of building sqft
                total += full["value_per_watt"] * building_sqft * 5

        return round(total, 0)
