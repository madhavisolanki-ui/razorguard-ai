"""Comprehensive ML Model Evaluation and Financial Impact Metrics."""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

from src.core.logging import get_logger

logger = get_logger("ml_evaluate")

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class ModelEvaluator:
    """Calculates empirical classification metrics, financial loss estimates, and scenario breakdowns."""

    # Default configurable cost assumptions
    DEFAULT_COST_FALSE_POSITIVE = 15.0  # USD / INR equivalent: lost customer lifetime value & support overhead
    DEFAULT_COST_FALSE_NEGATIVE = 50.0  # USD / INR equivalent: chargeback loss, interchange fees, dispute penalties

    @classmethod
    def evaluate_test_set(
        cls,
        y_true: np.ndarray,
        y_pred_probs: np.ndarray,
        threshold: float = 0.50,
        cost_fp: float = DEFAULT_COST_FALSE_POSITIVE,
        cost_fn: float = DEFAULT_COST_FALSE_NEGATIVE,
    ) -> Dict[str, Any]:
        """Calculates exact empirical performance metrics on a held-out test set."""
        y_pred = (y_pred_probs >= threshold).astype(int)

        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        precision = float(precision_score(y_true, y_pred, zero_division=0))
        recall = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))
        try:
            roc_auc = float(roc_auc_score(y_true, y_pred_probs))
        except ValueError:
            roc_auc = 0.0

        fpr = float(fp / max(1, fp + tn))
        fnr = float(fn / max(1, fn + tp))
        accuracy = float((tp + tn) / max(1, tp + tn + fp + fn))

        # Financial cost calculation
        total_fp_cost = round(fp * cost_fp, 2)
        total_fn_cost = round(fn * cost_fn, 2)
        total_financial_loss = round(total_fp_cost + total_fn_cost, 2)

        results = {
            "threshold": threshold,
            "total_test_samples": int(len(y_true)),
            "true_positives": int(tp),
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "false_positive_rate": round(fpr, 4),
            "false_negative_rate": round(fnr, 4),
            "financial_impact": {
                "cost_per_false_positive": cost_fp,
                "cost_per_false_negative": cost_fn,
                "total_false_positive_loss": total_fp_cost,
                "total_false_negative_loss": total_fn_cost,
                "net_financial_loss": total_financial_loss,
            },
        }

        # Save to disk
        metrics_file = RESULTS_DIR / "evaluation_metrics.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        # Save human-readable confusion matrix text
        matrix_text = (
            f"=== CONFUSION MATRIX (Threshold = {threshold}) ===\n"
            f"                     Predicted Legitimate    Predicted Fraud\n"
            f"Actual Legitimate:   TN = {tn:<19} FP = {fp}\n"
            f"Actual Fraud:        FN = {fn:<19} TP = {tp}\n\n"
            f"Metrics Summary:\n"
            f"Precision: {precision:.4f}\n"
            f"Recall:    {recall:.4f}\n"
            f"F1-Score:  {f1:.4f}\n"
            f"ROC-AUC:   {roc_auc:.4f}\n"
            f"FPR:       {fpr:.4f} ({fpr*100:.2f}%)\n"
            f"FNR:       {fnr:.4f} ({fnr*100:.2f}%)\n"
        )
        with open(RESULTS_DIR / "confusion_matrix.txt", "w", encoding="utf-8") as f:
            f.write(matrix_text)

        logger.info("Saved test evaluation metrics to: %s", metrics_file)
        return results

    @classmethod
    def evaluate_scenarios(
        cls,
        scenario_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Saves scenario benchmark results."""
        scenario_file = RESULTS_DIR / "scenario_benchmark.json"
        with open(scenario_file, "w", encoding="utf-8") as f:
            json.dump(scenario_results, f, indent=2)
        logger.info("Saved scenario benchmark to: %s", scenario_file)
        return scenario_results
