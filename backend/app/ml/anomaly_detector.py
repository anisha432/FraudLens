"""Anomaly detection using Isolation Forest."""
from __future__ import annotations

import os
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


def train_anomaly_detector(
    X_train: pd.DataFrame,
    feature_columns: List[str],
    model_dir: str,
    contamination: float = 0.05,
) -> Dict[str, Any]:
    """
    Train an Isolation Forest anomaly detector.
    
    Works independently of fraud labels — detects statistical outliers.
    """
    X = X_train[feature_columns].copy()
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    iso_forest.fit(X_scaled)
    
    # Save
    joblib.dump(iso_forest, os.path.join(model_dir, "anomaly_model.joblib"))
    joblib.dump(scaler, os.path.join(model_dir, "anomaly_scaler.joblib"))
    
    # Score the training data for baseline
    scores = iso_forest.decision_function(X_scaled)
    
    return {
        "model": iso_forest,
        "scaler": scaler,
        "features": feature_columns,
        "score_mean": float(scores.mean()),
        "score_std": float(scores.std()),
    }


def score_anomalies(
    df: pd.DataFrame,
    feature_columns: List[str],
    model_object: Dict[str, Any],
) -> pd.DataFrame:
    """
    Score transactions for anomalous behavior.
    
    Returns df with anomaly_score and is_anomaly columns added.
    """
    X = df[feature_columns].copy()
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    model = model_object["model"]
    scaler = model_object["scaler"]
    
    X_scaled = scaler.transform(X)
    
    # Raw anomaly score (lower = more anomalous)
    raw_scores = model.decision_function(X_scaled)
    
    # Normalize to 0-1 where 1 = most anomalous
    score_min = raw_scores.min()
    score_max = raw_scores.max()
    if score_max - score_min > 0:
        normalized_scores = 1 - (raw_scores - score_min) / (score_max - score_min)
    else:
        normalized_scores = np.ones(len(raw_scores)) * 0.5
    
    # Binary anomaly label
    predictions = model.predict(X_scaled)
    is_anomaly = (predictions == -1).astype(int)
    
    df = df.copy()
    df["anomaly_score"] = np.round(normalized_scores, 4)
    df["is_anomaly"] = is_anomaly
    
    return df


def score_single_transaction(
    features: Dict[str, float],
    feature_columns: List[str],
    model_object: Dict[str, Any],
) -> float:
    """Score a single transaction for anomaly."""
    X = np.array([[features.get(col, 0) for col in feature_columns]])
    X = np.nan_to_num(X, nan=0, posinf=0, neginf=0)
    
    model = model_object["model"]
    scaler = model_object["scaler"]
    
    X_scaled = scaler.transform(X)
    raw_score = model.decision_function(X_scaled)[0]
    
    # Convert: lower raw score = more anomalous → higher anomaly_score
    # Using a simple sigmoid-like transformation
    anomaly_score = 1 / (1 + np.exp(raw_score * 2))
    
    return round(float(anomaly_score), 4)
