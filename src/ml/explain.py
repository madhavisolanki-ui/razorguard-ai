"""SHAP Explainability Wrapper for XGBoost Fraud Predictions."""

from typing import List, Dict, Any, Optional
import numpy as np
import shap
import xgboost as xgb

from src.ml.features import ML_FEATURE_NAMES, FEATURE_HUMAN_NAMES
from src.core.logging import get_logger

logger = get_logger("shap_explainer")


class SHAPExplainer:
    """TreeSHAP explainer for computing exact feature attributions on XGBoost predictions."""

    def __init__(self, model: Optional[xgb.XGBClassifier] = None):
        self.model = model
        self.explainer: Optional[shap.TreeExplainer] = None
        if model is not None:
            self._init_explainer(model)

    def _init_explainer(self, model: xgb.XGBClassifier) -> None:
        self.model = model
        # Use TreeExplainer for sub-5ms exact TreeSHAP values
        self.explainer = shap.TreeExplainer(model)
        logger.info("SHAP TreeExplainer initialized successfully.")

    def explain_sample(
        self,
        feature_vector: np.ndarray,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Calculates SHAP feature contributions for a single transaction vector."""
        if self.explainer is None:
            raise RuntimeError("SHAP TreeExplainer is not initialized with a trained model.")

        if feature_vector.ndim == 1:
            feature_vector = feature_vector.reshape(1, -1)

        shap_values = self.explainer.shap_values(feature_vector)
        # For binary classification, shap_values is a 1D array or 2D [1, n_features]
        vals = shap_values[0] if shap_values.ndim > 1 else shap_values

        base_val = float(self.explainer.expected_value) if hasattr(self.explainer, "expected_value") else 0.0

        # Collate feature contributions
        contributions = []
        for idx, f_name in enumerate(ML_FEATURE_NAMES):
            s_val = float(vals[idx])
            raw_val = float(feature_vector[0, idx])
            contributions.append({
                "feature": f_name,
                "display_name": FEATURE_HUMAN_NAMES.get(f_name, f_name),
                "shap_value": round(s_val, 4),
                "raw_value": round(raw_val, 2),
                "direction": "RISK_INCREASING" if s_val > 0 else "RISK_DECREASING",
            })

        # Sort by absolute impact
        contributions.sort(key=lambda c: abs(c["shap_value"]), reverse=True)

        top_drivers = [c for c in contributions if c["shap_value"] > 0][:top_k]
        top_protective = [c for c in contributions if c["shap_value"] < 0][:top_k]

        # Generate human-readable explanation phrases
        driver_summaries = [
            f"{c['display_name']} ({c['raw_value']}) increased risk by +{round(c['shap_value'] * 100, 1)}%"
            for c in top_drivers
        ]

        return {
            "base_value": round(base_val, 4),
            "top_risk_drivers": top_drivers,
            "top_protective_signals": top_protective,
            "all_feature_attributions": contributions,
            "summary_bullet_points": driver_summaries,
        }
