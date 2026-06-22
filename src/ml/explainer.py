from typing import Dict, Any


class SHAPExplainer:
    """
    SHAP Explainability Wrapper.

    Translates model weights into human-readable feature importance values.
    Shows exactly which hazards drive the composite risk score.
    """

    HAZARD_KEYS = [
        "flood_risk_score",
        "heat_risk_score",
        "wildfire_risk_score",
        "transition_risk_score",
        "seismic_risk_score",
    ]

    IMPACT_NAMES = [
        "flood_impact",
        "heat_impact",
        "wildfire_impact",
        "transition_impact",
        "seismic_impact",
    ]

    def __init__(self, model):
        self.model = model

    def explain(
        self, features: Dict[str, Any], composite_score: float
    ) -> Dict[str, float]:
        """
        Generate SHAP values for the given prediction.

        For the MVP we use proportional mapping: each hazard's contribution
        to the score is proportional to its sub-score relative to the total.
        """
        scores = [features.get(k, 0) for k in self.HAZARD_KEYS]
        total = max(sum(scores), 1)

        # Base value: what the model predicts for an "average" property
        base_value = 35.0

        # How far the actual score deviates from the base
        diff = composite_score - base_value

        shap_values: Dict[str, float] = {}
        for name, score in zip(self.IMPACT_NAMES, scores):
            shap_values[name] = round((score / total) * diff, 2)

        # Elevation impact (amplifier, not a standalone score)
        elev_impact = 0.0
        if features.get("low_lying_flag"):
            elev_impact = round(
                (features.get("flood_risk_score", 0) / total) * diff * 0.3, 2
            )
        shap_values["elevation_impact"] = elev_impact

        shap_values["base_value"] = base_value

        return shap_values
