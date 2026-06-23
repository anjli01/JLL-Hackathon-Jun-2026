"""
ROI Calculator — estimates retrofit costs, energy savings, and payback periods.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Retrofit measure database (cost and savings per square foot)
# ---------------------------------------------------------------------------

RETROFIT_MEASURES = {
    "cool_roof": {
        "name": "Cool Roof Coating",
        "category": "heat_mitigation",
        "cost_per_sqft_low": 3.0,
        "cost_per_sqft_high": 5.0,
        "annual_savings_per_sqft_low": 0.50,
        "annual_savings_per_sqft_high": 0.80,
        "lifespan_years": 15,
        "applicable_hazards": ["heat"],
        "description": "Reflective roof coating to reduce cooling loads and roof surface temperature.",
    },
    "led_lighting": {
        "name": "LED Lighting Retrofit",
        "category": "energy_efficiency",
        "cost_per_sqft_low": 1.0,
        "cost_per_sqft_high": 2.0,
        "annual_savings_per_sqft_low": 0.40,
        "annual_savings_per_sqft_high": 0.60,
        "lifespan_years": 15,
        "applicable_hazards": ["transition"],
        "description": "Replace fluorescent/HID lighting with LED fixtures and controls.",
    },
    "heat_pump_ashp": {
        "name": "Air-Source Heat Pump (ASHP)",
        "category": "electrification",
        "cost_per_sqft_low": 15.0,
        "cost_per_sqft_high": 25.0,
        "annual_savings_per_sqft_low": 2.0,
        "annual_savings_per_sqft_high": 4.0,
        "lifespan_years": 20,
        "applicable_hazards": ["transition", "heat"],
        "description": "Electrify heating/cooling with high-efficiency air-source heat pumps.",
    },
    "solar_pv": {
        "name": "Rooftop Solar PV",
        "category": "renewable_energy",
        "cost_per_sqft_low": 8.0,
        "cost_per_sqft_high": 12.0,
        "annual_savings_per_sqft_low": 1.50,
        "annual_savings_per_sqft_high": 2.50,
        "lifespan_years": 25,
        "applicable_hazards": ["transition"],
        "description": "On-site solar photovoltaic system to offset grid electricity.",
    },
    "bms_upgrade": {
        "name": "Building Management System Upgrade",
        "category": "energy_efficiency",
        "cost_per_sqft_low": 2.0,
        "cost_per_sqft_high": 4.0,
        "annual_savings_per_sqft_low": 0.80,
        "annual_savings_per_sqft_high": 1.20,
        "lifespan_years": 15,
        "applicable_hazards": ["transition"],
        "description": "Smart controls for HVAC scheduling, fault detection, and demand response.",
    },
    "flood_barriers": {
        "name": "Flood Barriers & Shields",
        "category": "flood_mitigation",
        "cost_per_sqft_low": 5.0,
        "cost_per_sqft_high": 10.0,
        "annual_savings_per_sqft_low": 0.0,
        "annual_savings_per_sqft_high": 0.0,
        "lifespan_years": 20,
        "applicable_hazards": ["flood"],
        "description": "Deployable flood barriers for doorways, loading docks, and below-grade entries.",
        "risk_avoidance": True,
    },
    "elevated_mechanicals": {
        "name": "Elevated Mechanical Systems",
        "category": "flood_mitigation",
        "cost_per_sqft_low": 8.0,
        "cost_per_sqft_high": 15.0,
        "annual_savings_per_sqft_low": 0.0,
        "annual_savings_per_sqft_high": 0.0,
        "lifespan_years": 30,
        "applicable_hazards": ["flood"],
        "description": "Relocate HVAC, electrical, and generators above Base Flood Elevation.",
        "risk_avoidance": True,
    },
    "building_envelope": {
        "name": "Building Envelope Improvements",
        "category": "energy_efficiency",
        "cost_per_sqft_low": 5.0,
        "cost_per_sqft_high": 12.0,
        "annual_savings_per_sqft_low": 1.0,
        "annual_savings_per_sqft_high": 2.0,
        "lifespan_years": 25,
        "applicable_hazards": ["transition", "heat"],
        "description": "Insulation, window upgrades, and air sealing to reduce energy loads.",
    },
    "ember_resistant_roof": {
        "name": "Ember-Resistant Roofing",
        "category": "wildfire_mitigation",
        "cost_per_sqft_low": 8.0,
        "cost_per_sqft_high": 15.0,
        "annual_savings_per_sqft_low": 0.0,
        "annual_savings_per_sqft_high": 0.0,
        "lifespan_years": 30,
        "applicable_hazards": ["wildfire"],
        "description": "Class A fire-rated roofing with ember-resistant vents.",
        "risk_avoidance": True,
    },
    "seismic_retrofit": {
        "name": "Structural Seismic Retrofit",
        "category": "seismic_mitigation",
        "cost_per_sqft_low": 15.0,
        "cost_per_sqft_high": 50.0,
        "annual_savings_per_sqft_low": 0.0,
        "annual_savings_per_sqft_high": 0.0,
        "lifespan_years": 50,
        "applicable_hazards": ["seismic"],
        "description": "Structural strengthening (shear walls, steel bracing, foundation bolting) to resist earthquake forces.",
        "risk_avoidance": True,
    },
    "non_structural_bracing": {
        "name": "Non-Structural Seismic Bracing",
        "category": "seismic_mitigation",
        "cost_per_sqft_low": 2.0,
        "cost_per_sqft_high": 5.0,
        "annual_savings_per_sqft_low": 0.0,
        "annual_savings_per_sqft_high": 0.0,
        "lifespan_years": 30,
        "applicable_hazards": ["seismic"],
        "description": "Anchor mechanical equipment, brace ceilings and partitions, secure furniture for earthquake resilience.",
        "risk_avoidance": True,
    },
}


class ROICalculator:
    """Estimates retrofit costs, savings, and payback for recommended measures."""

    def __init__(self):
        self.measures = RETROFIT_MEASURES

    def calculate_roi(
        self,
        measure_id: str,
        building_sqft: int = 50000,
        climate_zone: int = 4,
    ) -> dict:
        """
        Calculate ROI for a specific retrofit measure.

        Returns dict with cost_estimate, annual_savings, payback_years,
        npv_10yr, and measure details.
        """
        measure = self.measures.get(measure_id)
        if not measure:
            return {"error": f"Unknown measure: {measure_id}"}

        # Climate zone adjustment factor (hot = more cooling savings, cold = more heating savings)
        climate_factor = 1.0
        if climate_zone <= 2:
            climate_factor = 1.2 if "heat" in measure["applicable_hazards"] else 1.0
        elif climate_zone >= 5:
            climate_factor = 1.15 if "transition" in measure["applicable_hazards"] else 0.9

        cost_low = measure["cost_per_sqft_low"] * building_sqft
        cost_high = measure["cost_per_sqft_high"] * building_sqft
        cost_mid = (cost_low + cost_high) / 2

        savings_low = measure["annual_savings_per_sqft_low"] * building_sqft * climate_factor
        savings_high = measure["annual_savings_per_sqft_high"] * building_sqft * climate_factor
        savings_mid = (savings_low + savings_high) / 2

        # Payback calculation
        is_risk_avoidance = measure.get("risk_avoidance", False)
        if is_risk_avoidance or savings_mid == 0:
            payback_years = None
        else:
            payback_years = round(cost_mid / savings_mid, 1)

        # Simple NPV at 5% discount rate over 10 years
        discount_rate = 0.05
        npv = -cost_mid
        for year in range(1, 11):
            npv += savings_mid / ((1 + discount_rate) ** year)
        npv = round(npv, 0)

        return {
            "measure_id": measure_id,
            "name": measure["name"],
            "category": measure["category"],
            "description": measure["description"],
            "cost_estimate_low": round(cost_low),
            "cost_estimate_high": round(cost_high),
            "cost_estimate_mid": round(cost_mid),
            "annual_savings_low": round(savings_low),
            "annual_savings_high": round(savings_high),
            "annual_savings_mid": round(savings_mid),
            "payback_years": payback_years,
            "npv_10yr": npv,
            "lifespan_years": measure["lifespan_years"],
            "is_risk_avoidance": is_risk_avoidance,
            "building_sqft": building_sqft,
            "climate_zone": climate_zone,
        }

    def get_measures_for_hazard(self, hazard: str) -> list[str]:
        """Return measure IDs applicable to a given hazard."""
        return [
            mid
            for mid, m in self.measures.items()
            if hazard in m["applicable_hazards"]
        ]

    def calculate_portfolio_roi(
        self,
        measures: list[str],
        building_sqft: int = 50000,
        climate_zone: int = 4,
    ) -> dict:
        """Calculate combined ROI for multiple measures."""
        results = []
        total_cost = 0
        total_savings = 0

        for measure_id in measures:
            roi = self.calculate_roi(measure_id, building_sqft, climate_zone)
            if "error" not in roi:
                results.append(roi)
                total_cost += roi["cost_estimate_mid"]
                total_savings += roi["annual_savings_mid"]

        overall_payback = round(total_cost / total_savings, 1) if total_savings > 0 else None

        return {
            "measures": results,
            "total_cost_estimate": round(total_cost),
            "total_annual_savings": round(total_savings),
            "overall_payback_years": overall_payback,
            "ten_year_net_savings": round(total_savings * 10 - total_cost),
        }
