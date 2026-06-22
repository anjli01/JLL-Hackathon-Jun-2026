"""
Unit tests for the ML scoring engine and SHAP explainer.
"""
from src.ml.xgboost_ensemble import XGBoostEnsemble
from src.ml.explainer import SHAPExplainer


def test_composite_score_bounded():
    """Composite score must always be in [0, 100]."""
    model = XGBoostEnsemble()

    # High-risk property
    high_risk = {
        "flood_risk_score": 95, "heat_risk_score": 90,
        "wildfire_risk_score": 80, "transition_risk_score": 90,
        "seismic_risk_score": 85,
        "is_sfha": True, "compliance_gap_flag": True,
        "low_lying_flag": True, "energy_risk_flag": True,
    }
    pred = model.predict(high_risk)
    assert 0 <= pred["composite_score"] <= 100

    # Low-risk property
    low_risk = {
        "flood_risk_score": 5, "heat_risk_score": 0,
        "wildfire_risk_score": 0, "transition_risk_score": 10,
        "seismic_risk_score": 5,
        "is_sfha": False, "compliance_gap_flag": False,
        "low_lying_flag": False, "energy_risk_flag": False,
    }
    pred = model.predict(low_risk)
    assert 0 <= pred["composite_score"] <= 100


def test_sub_scores_includes_seismic_and_elevation():
    """Sub-scores should include the new seismic and elevation dimensions."""
    model = XGBoostEnsemble()
    features = {
        "flood_risk_score": 60, "heat_risk_score": 40,
        "wildfire_risk_score": 20, "transition_risk_score": 80,
        "seismic_risk_score": 50, "low_lying_flag": True,
    }
    pred = model.predict(features)
    assert "seismic" in pred["sub_scores"]
    assert "elevation" in pred["sub_scores"]
    assert pred["sub_scores"]["seismic"] == 50
    # low_lying_flag means elevation component = flood_risk_score
    assert pred["sub_scores"]["elevation"] == 60


def test_eal_proportional_to_score():
    """Expected annual loss should scale with the composite score."""
    model = XGBoostEnsemble()
    low = model.predict({"flood_risk_score": 10, "heat_risk_score": 5, "wildfire_risk_score": 0, "transition_risk_score": 5, "seismic_risk_score": 5})
    high = model.predict({"flood_risk_score": 90, "heat_risk_score": 80, "wildfire_risk_score": 70, "transition_risk_score": 85, "seismic_risk_score": 80})
    assert high["eal_usd"] > low["eal_usd"]


def test_sfha_amplifies_score():
    """SFHA flag should increase the composite score."""
    model = XGBoostEnsemble()
    base = {"flood_risk_score": 50, "heat_risk_score": 50, "wildfire_risk_score": 50, "transition_risk_score": 50, "seismic_risk_score": 50}
    without = model.predict({**base, "is_sfha": False})
    with_sfha = model.predict({**base, "is_sfha": True})
    assert with_sfha["composite_score"] >= without["composite_score"]


def test_low_lying_amplifies_flood_risk():
    """Low-lying flag should amplify the flood component."""
    model = XGBoostEnsemble()
    base = {"flood_risk_score": 80, "heat_risk_score": 30, "wildfire_risk_score": 10, "transition_risk_score": 30, "seismic_risk_score": 20}
    without = model.predict({**base, "low_lying_flag": False})
    with_low = model.predict({**base, "low_lying_flag": True})
    assert with_low["composite_score"] > without["composite_score"]


def test_shap_includes_seismic_and_elevation():
    """SHAP output should include seismic and elevation impact."""
    model = XGBoostEnsemble()
    explainer = SHAPExplainer(model)
    features = {
        "flood_risk_score": 60, "heat_risk_score": 40,
        "wildfire_risk_score": 20, "transition_risk_score": 50,
        "seismic_risk_score": 70, "low_lying_flag": True,
    }
    pred = model.predict(features)
    shap = explainer.explain(features, pred["composite_score"])
    assert "seismic_impact" in shap
    assert "elevation_impact" in shap
    assert "base_value" in shap


def test_shap_base_value_present():
    """SHAP output must include a base_value."""
    model = XGBoostEnsemble()
    explainer = SHAPExplainer(model)
    features = {"flood_risk_score": 30, "heat_risk_score": 30, "wildfire_risk_score": 30, "transition_risk_score": 30, "seismic_risk_score": 30}
    shap = explainer.explain(features, model.predict(features)["composite_score"])
    assert shap["base_value"] > 0
