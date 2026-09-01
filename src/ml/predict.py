"""ML Inference Service for XGBoost, Isolation Forest, and SHAP."""

import time
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import xgboost as xgb

from src.core.config import settings
from src.core.logging import get_logger
from src.features.calculator import FeatureVector
from src.ml.features import extract_feature_array, ML_FEATURE_NAMES
from src.ml.anomaly import AnomalyDetector
from src.ml.explain import SHAPExplainer

logger = get_logger("ml_predict")


class MLInferenceService:
    """Synchronous low-latency inference engine serving XGBoost, Isolation Forest, and SHAP."""

    def __init__(
        self,
        xgboost_path: Optional[Path] = None,
        iforest_path: Optional[Path] = None,
    ):
        self.xgboost_path = xgboost_path or (settings.MODELS_DIR / "xgboost_fraud_model.json")
        self.iforest_path = iforest_path or (settings.MODELS_DIR / "isolation_forest_model.joblib")

        self.xgb_model: Optional[xgb.XGBClassifier] = None
        self.anomaly_detector: Optional[AnomalyDetector] = None
        self.shap_explainer: Optional[SHAPExplainer] = None

        self._load_models_if_available()

    def _load_models_if_available(self) -> None:
        """Loads serialized models if they exist on disk."""
        if self.xgboost_path.exists():
            try:
                self.xgb_model = xgb.XGBClassifier()
                self.xgb_model.load_model(str(self.xgboost_path))
                self.shap_explainer = SHAPExplainer(self.xgb_model)
                logger.info("Loaded XGBoost model from: %s", self.xgboost_path)
            except Exception as e:
                logger.warning("Failed to load XGBoost model from %s: %s", self.xgboost_path, str(e))

        if self.iforest_path.exists():
            try:
                self.anomaly_detector = AnomalyDetector()
                self.anomaly_detector.load(self.iforest_path)
                logger.info("Loaded Isolation Forest model from: %s", self.iforest_path)
            except Exception as e:
                logger.warning("Failed to load Isolation Forest model from %s: %s", self.iforest_path, str(e))

    def predict_features(self, features: FeatureVector) -> Dict[str, Any]:
        """Runs ML inference on a FeatureVector."""
        arr = extract_feature_array(features)
        return self.predict_array(arr)

    def predict_array(self, feature_array: np.ndarray) -> Dict[str, Any]:
        """Runs XGBoost fraud classification, Isolation Forest anomaly scoring, and SHAP attribution."""
        start_time = time.perf_counter()

        if feature_array.ndim == 1:
            feature_array = feature_array.reshape(1, -1)

        # 1. XGBoost Fraud Probability
        fraud_prob = 0.05
        if self.xgb_model is not None:
            try:
                probs = self.xgb_model.predict_proba(feature_array)
                # Binary classification: index 1 is positive fraud probability
                fraud_prob = float(probs[0, 1])
            except Exception as e:
                logger.error("XGBoost prediction error: %s", str(e))
                fraud_prob = 0.10

        # 2. Isolation Forest Anomaly Score
        anomaly_score = 0.10
        if self.anomaly_detector is not None and self.anomaly_detector.is_fitted:
            try:
                scores = self.anomaly_detector.score_samples(feature_array)
                anomaly_score = float(scores[0])
            except Exception as e:
                logger.error("Isolation Forest scoring error: %s", str(e))
                anomaly_score = 0.15

        # 3. SHAP TreeExplainer Attributions
        shap_data: Dict[str, Any] = {"top_risk_drivers": [], "summary_bullet_points": []}
        if self.shap_explainer is not None:
            try:
                shap_data = self.shap_explainer.explain_sample(feature_array, top_k=5)
            except Exception as e:
                logger.warning("SHAP explanation error: %s", str(e))

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "fraud_probability": round(fraud_prob, 4),
            "anomaly_score": round(anomaly_score, 4),
            "shap_explanation": shap_data,
            "inference_latency_ms": latency_ms,
        }
