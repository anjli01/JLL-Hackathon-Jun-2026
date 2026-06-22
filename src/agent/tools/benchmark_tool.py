"""
Benchmark Tool — compares building energy performance against ENERGY STAR peers.
"""


class BenchmarkTool:
    """Compares a property's energy performance against national benchmarks."""

    # National median EUI by building type (source kBtu/sq ft/year)
    NATIONAL_MEDIANS = {
        "office": 92.9,
        "retail": 79.7,
        "hotel": 104.7,
        "school": 64.3,
        "hospital": 389.9,
        "multifamily": 96.1,
        "warehouse": 31.9,
        "supermarket": 200.5,
    }

    # Top-quartile (ENERGY STAR ≥75) EUI by building type
    TOP_QUARTILE = {
        "office": 60.0,
        "retail": 52.0,
        "hotel": 72.0,
        "school": 42.0,
        "hospital": 280.0,
        "multifamily": 62.0,
        "warehouse": 20.0,
        "supermarket": 140.0,
    }

    def benchmark(
        self,
        building_type: str = "office",
        current_eui: float = 92.9,
        climate_zone: int = 4,
    ) -> dict:
        """
        Compare building EUI against national benchmarks.

        Returns percentile estimate, improvement potential, and
        whether ENERGY STAR certification is likely.
        """
        bt = building_type.lower()
        median = self.NATIONAL_MEDIANS.get(bt, 92.9)
        top_q = self.TOP_QUARTILE.get(bt, 60.0)

        # Climate adjustment (hot climates use more, cold climates use more heating)
        climate_multiplier = {1: 1.15, 2: 1.10, 3: 1.05, 4: 1.0, 5: 1.05, 6: 1.10, 7: 1.15}
        adjusted_median = median * climate_multiplier.get(climate_zone, 1.0)

        # Estimate percentile
        if current_eui <= top_q:
            percentile = 85  # Top performer
        elif current_eui <= adjusted_median * 0.75:
            percentile = 75  # ENERGY STAR eligible
        elif current_eui <= adjusted_median:
            percentile = 50  # Average
        elif current_eui <= adjusted_median * 1.3:
            percentile = 30  # Below average
        else:
            percentile = 15  # Poor performer

        # Improvement potential
        improvement_pct = max(0, round((current_eui - top_q) / current_eui * 100, 1))

        # Estimated savings if improved to top quartile
        savings_kbtu = max(0, current_eui - top_q)
        # Rough conversion: $0.015 per kBtu
        savings_per_sqft = round(savings_kbtu * 0.015, 2)

        return {
            "building_type": bt,
            "current_eui": current_eui,
            "national_median_eui": median,
            "climate_adjusted_median_eui": round(adjusted_median, 1),
            "top_quartile_eui": top_q,
            "estimated_percentile": percentile,
            "energy_star_eligible": percentile >= 75,
            "improvement_potential_pct": improvement_pct,
            "savings_per_sqft_usd": savings_per_sqft,
            "climate_zone": climate_zone,
            "recommendation": self._get_recommendation(percentile),
        }

    @staticmethod
    def _get_recommendation(percentile: int) -> str:
        if percentile >= 75:
            return "Pursue ENERGY STAR certification. Consider LEED for additional differentiation."
        elif percentile >= 50:
            return "Implement BMS optimization and LED lighting to reach ENERGY STAR threshold."
        elif percentile >= 30:
            return "Significant improvement needed. Prioritize retro-commissioning, HVAC upgrades, and lighting."
        else:
            return "Major retrofit required. Consider comprehensive energy audit and staged improvement plan."
