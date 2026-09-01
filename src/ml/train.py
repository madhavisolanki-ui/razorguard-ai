"""End-to-End Model Training Pipeline for XGBoost and Isolation Forest."""

import datetime
import json
import time
import sys
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import xgboost as xgb

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.config import settings
from src.core.logging import get_logger
from src.generator.stream_simulator import StreamSimulator
from src.generator.scenarios import ScenarioGenerator
from src.ml.features import dataframe_to_features, extract_feature_array, ML_FEATURE_NAMES
from src.ml.anomaly import AnomalyDetector
from src.ml.evaluate import ModelEvaluator
from src.ml.composite_scorer import UnifiedRiskScorer
from src.features.calculator import FeatureCalculator
from src.database.repository import Repository
from src.core.database import SessionLocal

logger = get_logger("ml_train")


def train_models(
    n_samples: int = 50000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Generates synthetic dataset, trains XGBoost & Isolation Forest, evaluates and serializes artifacts."""
    logger.info("Starting ML model training pipeline with %d synthetic samples...", n_samples)
    t_start = time.perf_counter()

    # -------------------------------------------------------------
    # 1. Dataset Generation
    # -------------------------------------------------------------
    simulator = StreamSimulator(seed=seed)
    events = simulator.generate_events(count=n_samples)
    df = simulator.events_to_dataframe(events)

    X, y, feature_names = dataframe_to_features(df)
    logger.info("Extracted feature matrix: X=%s, y=%s (Fraud/Abuse count: %d)", X.shape, y.shape, int(y.sum()))

    # -------------------------------------------------------------
    # 2. Strict Entity-Disjoint Train / Validation / Test Split
    # -------------------------------------------------------------
    # Split by user_id to guarantee zero entity overlap / leakage between train and test
    unique_users = np.array(df["user_id"].unique().tolist())
    train_users, temp_users = train_test_split(unique_users, test_size=0.30, random_state=seed)
    val_users, test_users = train_test_split(temp_users, test_size=0.50, random_state=seed)

    train_mask = df["user_id"].isin(train_users).values
    val_mask = df["user_id"].isin(val_users).values
    test_mask = df["user_id"].isin(test_users).values

    X_train, y_train = X[train_mask], y[train_mask]
    X_val, y_val = X[val_mask], y[val_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    logger.info("Entity-Disjoint Split: Train=%d, Validation=%d, Test=%d (Zero user overlap)", len(X_train), len(X_val), len(X_test))

    # -------------------------------------------------------------
    # 3. Supervised XGBoost Classifier Training
    # -------------------------------------------------------------
    logger.info("Training Supervised XGBoost Classifier...")
    pos_count = int(y_train.sum())
    neg_count = len(y_train) - pos_count
    scale_weight = float(neg_count / max(1, pos_count))

    xgb_model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.08,
        scale_pos_weight=scale_weight,
        subsample=0.85,
        colsample_bytree=0.85,
        eval_metric="logloss",
        random_state=seed,
        n_jobs=-1,
        early_stopping_rounds=15,
    )

    xgb_model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    xgb_path = settings.MODELS_DIR / "xgboost_fraud_model.json"
    xgb_model.save_model(str(xgb_path))
    logger.info("Saved XGBoost model to: %s", xgb_path)

    # -------------------------------------------------------------
    # 4. Unsupervised Isolation Forest Training
    # -------------------------------------------------------------
    logger.info("Training Unsupervised Isolation Forest...")
    anomaly_detector = AnomalyDetector(
        n_estimators=100,
        contamination=0.15,
        random_state=seed,
    )
    # Train on training partition
    anomaly_detector.fit(X_train)

    iforest_path = settings.MODELS_DIR / "isolation_forest_model.joblib"
    anomaly_detector.save(iforest_path)

    # -------------------------------------------------------------
    # 5. Held-out Test Set Evaluation
    # -------------------------------------------------------------
    logger.info("Evaluating models on held-out test set (%d samples)...", len(X_test))
    test_pred_probs = xgb_model.predict_proba(X_test)[:, 1]
    evaluation_metrics = ModelEvaluator.evaluate_test_set(y_test, test_pred_probs, threshold=0.50)

    # -------------------------------------------------------------
    # 6. Model Versioning Metadata
    # -------------------------------------------------------------
    metadata = {
        "model_version": "1.0.0",
        "training_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "feature_version": "2.0",
        "dataset_version": f"synthetic_v1_{n_samples}",
        "config_version": "1.0",
        "feature_names": ML_FEATURE_NAMES,
        "train_samples": int(len(X_train)),
        "validation_samples": int(len(X_val)),
        "test_samples": int(len(X_test)),
        "metrics_summary": {
            "precision": evaluation_metrics["precision"],
            "recall": evaluation_metrics["recall"],
            "f1_score": evaluation_metrics["f1_score"],
            "roc_auc": evaluation_metrics["roc_auc"],
            "false_positive_rate": evaluation_metrics["false_positive_rate"],
        }
    }

    meta_path = settings.MODELS_DIR / "feature_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Saved model versioning metadata to: %s", meta_path)

    # -------------------------------------------------------------
    # 7. Scenario-by-Scenario Evaluation
    # -------------------------------------------------------------
    logger.info("Running Scenario Evaluation across all 6 canonical traffic classes...")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.core.database import Base
    from src.database.init_db import DEFAULT_MERCHANTS

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    repo = Repository(db)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    scenario_gen = ScenarioGenerator(seed=seed)
    calc = FeatureCalculator(repo)
    scorer = UnifiedRiskScorer()

    scenarios = [
        "normal",
        "legitimate_spike",
        "bot_abuse",
        "payment_abuse",
        "coordinated_abuse",
        "fraud_ring",
    ]

    scenario_metrics = {}

    for s_name in scenarios:
        s_scores = []
        s_actions = []
        s_fraud_probs = []
        s_anomaly_scores = []

        for _ in range(50):
            event = scenario_gen.generate_by_scenario_name(s_name)
            fv = calc.calculate_features(event)
            decision = scorer.evaluate(fv)

            s_scores.append(decision.risk_score)
            s_actions.append(decision.recommended_action)
            s_fraud_probs.append(decision.fraud_probability)
            s_anomaly_scores.append(decision.anomaly_score)

        scenario_metrics[s_name] = {
            "scenario": s_name,
            "sample_count": 50,
            "mean_risk_score": round(float(np.mean(s_scores)), 1),
            "median_risk_score": round(float(np.median(s_scores)), 1),
            "mean_fraud_prob": round(float(np.mean(s_fraud_probs)), 3),
            "mean_anomaly_score": round(float(np.mean(s_anomaly_scores)), 3),
            "action_distribution": {
                act: round(float(s_actions.count(act) / len(s_actions)), 2)
                for act in set(s_actions)
            },
            "allow_rate": round(float(s_actions.count("ALLOW") / len(s_actions)), 2),
            "block_throttle_rate": round(float((s_actions.count("RATE_LIMIT") + s_actions.count("STEP_UP_VERIFICATION")) / len(s_actions)), 2),
        }

    db.close()
    ModelEvaluator.evaluate_scenarios(scenario_metrics)

    elapsed = round(time.perf_counter() - t_start, 2)
    logger.info("Training & Evaluation pipeline completed successfully in %.2f seconds.", elapsed)

    return {
        "training_time_sec": elapsed,
        "evaluation_metrics": evaluation_metrics,
        "scenario_metrics": scenario_metrics,
        "metadata": metadata,
    }


if __name__ == "__main__":
    res = train_models(n_samples=10000)
    print("\nTraining Finished!")
    print("Test Set Metrics:", res["evaluation_metrics"])
    print("\nScenario Summary:")
    for sc, data in res["scenario_metrics"].items():
        print(f"[{sc.upper()}] Mean Risk Score: {data['mean_risk_score']} | Actions: {data['action_distribution']}")
