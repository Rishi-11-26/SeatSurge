"""
SeatSurge ML Bot Detection — Training & Evaluation Pipeline.
============================================================
Trains a Scikit-Learn Classifier to detect malicious scalper bots.
Evaluates on a held-out test dataset and writes model artifacts & metrics.
"""

import json
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)
import joblib

from app.ml.dataset import generate_session_dataset, FEATURE_COLUMNS

MODEL_PATH = Path(__file__).resolve().parent / "bot_model.joblib"
METRICS_PATH = Path(__file__).resolve().parent / "model_metrics.json"


def train_and_evaluate_model():
    print("[ML] Generating synthetic session dataset (3,000 samples)...")
    df = generate_session_dataset(n_samples=3000, bot_ratio=0.5, random_state=42)

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    # 70% Train, 30% Held-Out Test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )

    print(f"[ML] Training set size: {len(X_train)}, Held-out test set size: {len(X_test)}")

    # Train Random Forest Classifier
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_split=5,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X_train, y_train)

    # Predictions on held-out test set
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    # Compute authoritative evaluation metrics
    prec = float(precision_score(y_test, y_pred))
    rec = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_prob))
    cm = confusion_matrix(y_test, y_pred).tolist()

    print("\n" + "=" * 60)
    print("SEATSURGE ML BOT DETECTION MODEL EVALUATION (HELD-OUT TEST SET)")
    print("=" * 60)
    print(f"Precision:         {prec:.4f}")
    print(f"Recall:            {rec:.4f}")
    print(f"F1-Score:          {f1:.4f}  (Requirement: F1 >= 0.80)")
    print(f"ROC-AUC:           {roc_auc:.4f}")
    print("Confusion Matrix:")
    print(f"  [TN: {cm[0][0]}, FP: {cm[0][1]}]")
    print(f"  [FN: {cm[1][0]}, TP: {cm[1][1]}]")
    print("-" * 60)
    print("Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Human (0)", "Bot (1)"]))
    print("=" * 60 + "\n")

    assert f1 >= 0.80, f"Model F1-score {f1:.4f} is below target 0.80"

    # Feature importances
    importances = dict(zip(FEATURE_COLUMNS, [float(x) for x in clf.feature_importances_]))
    sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

    metrics_payload = {
        "model_type": "RandomForestClassifier",
        "n_samples": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": roc_auc,
        "confusion_matrix": {
            "true_negatives": cm[0][0],
            "false_positives": cm[0][1],
            "false_negatives": cm[1][0],
            "true_positives": cm[1][1],
        },
        "feature_importances": sorted_importances,
    }

    # Save model artifact and metrics file
    joblib.dump(clf, MODEL_PATH)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_payload, f, indent=2)

    print(f"[ML] Successfully saved model artifact to: {MODEL_PATH}")
    print(f"[ML] Successfully saved metrics report to: {METRICS_PATH}")
    return clf, metrics_payload


if __name__ == "__main__":
    train_and_evaluate_model()
