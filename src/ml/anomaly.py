"""Unsupervised Isolation Forest Behavioral Anomaly Detector."""

import joblib
from pathlib import Path
from typing import Optional, Union
import numpy as np
from sklearn.ensemble import IsolationForest

from src.core.logging import get_logger

logger = get_logger("anomaly_detector")


class AnomalyDetector:
    """Isolation Forest anomaly detection wrapper for identifying zero-day and volume anomalies."""

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float = 0.15,
        random_state: int = 42,
    ):
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray) -> "AnomalyDetector":
        """Trains Isolation Forest on feature matrix X."""
        logger.info("Training Isolation Forest on %d samples with %d features...", X.shape[0], X.shape[1])
        self.model.fit(X)
        self.is_fitted = True
        logger.info("Isolation Forest training complete.")
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """Computes normalized anomaly score in [0.0, 1.0].
        
        Higher values (e.g. > 0.65) indicate severe behavioral/volume anomalies.
        """
        if not self.is_fitted:
            raise RuntimeError("AnomalyDetector model is not fitted yet.")

        if X.ndim == 1:
            X = X.reshape(1, -1)

        # decision_function: positive for inliers, negative for outliers
        raw_scores = self.model.decision_function(X)

        # Calibrated logistic sigmoid normalization:
        # normal samples (> 0.10) map to ~0.05-0.15
        # borderline samples (~0.0) map to ~0.35-0.50
        # severe anomalies (< -0.15) map to ~0.75-0.95
        normalized_scores = 1.0 / (1.0 + np.exp((raw_scores + 0.05) * 12.0))
        return np.round(np.clip(normalized_scores, 0.0, 1.0), 3)

    def save(self, filepath: Path) -> None:
        """Serializes model artifact to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, filepath)
        logger.info("Saved Isolation Forest model to: %s", filepath)

    def load(self, filepath: Path) -> "AnomalyDetector":
        """Loads serialized model artifact from disk."""
        if not filepath.exists():
            raise FileNotFoundError(f"Isolation Forest model file not found at: {filepath}")
        self.model = joblib.load(filepath)
        self.is_fitted = True
        logger.info("Loaded Isolation Forest model from: %s", filepath)
        return self
