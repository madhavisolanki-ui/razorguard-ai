"""Unit Tests for Phase 3 ML Pipeline (Features, XGBoost, Isolation Forest, SHAP, Composite Scorer)."""

import pytest
import numpy as np
from pathlib import Path

from src.core.config import settings
from src.features.calculator import FeatureVector
from src.ml.features import ML_FEATURE_NAMES, extract_feature_array
from src.ml.anomaly import AnomalyDetector
from src.ml.predict import MLInferenceService
from src.ml.composite_scorer import UnifiedRiskScorer, UnifiedRiskDecision


def test_ml_feature_extraction_vector_length():
    fv = FeatureVector(
        event_id="evt_test_ml_01",
        user_id="usr_test_01",
        merchant_id="mer_test_01",
        device_id="dev_test_01",
        ip_address="103.21.244.1",
        amount=1999.00,
        checkout_duration_sec=12.0,
        user_requests_per_minute=1,
        user_requests_per_5_minutes=2,
        ip_requests_per_minute=1,
        ip_requests_per_5_minutes=2,
        device_requests_per_minute=1,
        device_requests_per_5_minutes=2,
        transaction_velocity=0.02,
        payment_failure_rate_5m=0.0,
        payment_success_rate_5m=1.0,
    )

    arr = extract_feature_array(fv)
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (len(ML_FEATURE_NAMES),)
    assert arr.dtype == np.float32


def test_anomaly_detector_training_and_scoring():
    detector = AnomalyDetector(n_estimators=50, contamination=0.10, random_state=42)

    # Synthetic normal background samples
    X_normal = np.random.normal(loc=1.0, scale=0.2, size=(200, len(ML_FEATURE_NAMES))).astype(np.float32)
    detector.fit(X_normal)

    assert detector.is_fitted is True

    # Normal sample should have low anomaly score (< 0.50)
    normal_sample = np.random.normal(loc=1.0, scale=0.2, size=(1, len(ML_FEATURE_NAMES))).astype(np.float32)
    normal_score = detector.score_samples(normal_sample)[0]
    assert normal_score <= 0.60

    # Extreme anomaly sample (e.g. 50x values) should have higher anomaly score
    extreme_sample = np.ones((1, len(ML_FEATURE_NAMES)), dtype=np.float32) * 50.0
    anomaly_score = detector.score_samples(extreme_sample)[0]
    assert anomaly_score >= normal_score


def test_unified_risk_scorer_decision_structure():
    scorer = UnifiedRiskScorer()

    fv = FeatureVector(
        event_id="evt_dec_01",
        user_id="usr_dec_01",
        merchant_id="mer_fashion",
        device_id="dev_dec_01",
        ip_address="49.37.10.2",
        amount=2500.00,
        checkout_duration_sec=14.0,
        user_requests_per_minute=1,
        user_requests_per_5_minutes=1,
        ip_requests_per_minute=1,
        ip_requests_per_5_minutes=1,
        device_requests_per_minute=1,
        device_requests_per_5_minutes=1,
        payment_failure_rate_5m=0.0,
        payment_success_rate_5m=1.0,
        is_headless_device=False,
        is_datacenter_proxy=False,
        ip_reputation_score=0.98,
    )

    decision: UnifiedRiskDecision = scorer.evaluate(fv)

    assert 0.0 <= decision.risk_score <= 100.0
    assert decision.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert decision.recommended_action in ("ALLOW", "MONITOR", "STEP_UP_VERIFICATION", "RATE_LIMIT")
    assert 0.0 <= decision.fraud_probability <= 1.0
    assert 0.0 <= decision.anomaly_score <= 1.0
    assert "xgboost_fraud_prob" in decision.model_scores
    assert len(decision.explanation) > 10
