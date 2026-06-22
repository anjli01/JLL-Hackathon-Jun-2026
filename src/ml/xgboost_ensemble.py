import numpy as np
import pandas as pd
from typing import Dict, Any


class XGBoostEnsemble:
    """
    XGBoost-style ensemble for hackathon MVP.

    Combines 6 hazard sub-scores into a composite risk score (0-100)
    using weighted non-linear logic that simulates tree-based interactions.
    In production, this would load trained .json XGBoost models.
    """

    # Hazard weights — sum to 1.0
    WEIGHTS = {
        "flood":      0.30,
        "heat":       0.15,
        "wildfire":   0.15,
        "transition": 0.10,
        "seismic":    0.15,
        "elevation":  0.15,  # elevation acts as a flood-risk amplifier
    }

    def __init__(self):
        self.feature_names = [
            "flood_risk_score", "heat_risk_score",
            "wildfire_risk_score", "transition_risk_score",
            "seismic_risk_score",
            "is_sfha", "compliance_gap_flag",
            "low_lying_flag", "energy_risk_flag",
        ]

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate composite risk score from all hazard sub-scores.
        """
        f_score = features.get("flood_risk_score", 0)
        h_score = features.get("heat_risk_score", 0)
        w_score = features.get("wildfire_risk_score", 0)
        t_score = features.get("transition_risk_score", 0)
        s_score = features.get("seismic_risk_score", 0)

        # Elevation contributes as a flood amplifier:
        # low-lying properties get a penalty equal to the flood score
        elev_component = f_score if features.get("low_lying_flag") else 0

        base_score = (
            f_score * self.WEIGHTS["flood"]
            + h_score * self.WEIGHTS["heat"]
            + w_score * self.WEIGHTS["wildfire"]
            + t_score * self.WEIGHTS["transition"]
            + s_score * self.WEIGHTS["seismic"]
            + elev_component * self.WEIGHTS["elevation"]
        )

        # Non-linear amplifiers (simulating tree interactions)
        if features.get("is_sfha"):
            base_score *= 1.15

        if features.get("compliance_gap_flag"):
            base_score *= 1.08

        if features.get("energy_risk_flag"):
            base_score *= 1.05

        composite_score = min(max(int(base_score), 0), 100)

        # Map to expected annual loss (EAL) in USD
        eal_usd = composite_score * 1500

        return {
            "composite_score": composite_score,
            "eal_usd": eal_usd,
            "sub_scores": {
                "flood": f_score,
                "heat": h_score,
                "wildfire": w_score,
                "transition": t_score,
                "seismic": s_score,
                "elevation": elev_component,
            },
        }
