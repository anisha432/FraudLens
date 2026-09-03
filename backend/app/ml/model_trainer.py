"""Model training, evaluation, and threshold optimization."""
from __future__ import annotations

import json
import os
import warnings
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    average_precision_score, confusion_matrix, classification_report,
    roc_curve, precision_recall_curve,
)
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

warnings.filterwarnings("ignore")


def train_models(
    df: pd.DataFrame,
    feature_columns: List[str],
    target_column: str,
    model_dir: str = "./models_artifacts",
    test_size: float = 0.2,
    use_smote: bool = True,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Train multiple fraud detection models.
    
    Returns comprehensive training results including metrics, thresholds, etc.
    """
    os.makedirs(model_dir, exist_ok=True)
    
    # Prepare data
    X = df[feature_columns].copy()
    y = df[target_column].copy()
    
    # Handle any remaining NaN/inf
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)
    y = y.fillna(0).astype(int)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y if y.sum() > 5 else None
    )
    
    # Store test data for later use
    test_data = {
        "X_test": X_test,
        "y_test": y_test,
    }
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Handle class imbalance
    X_train_resampled = X_train_scaled
    y_train_resampled = y_train
    
    if use_smote and y_train.sum() >= 5 and len(y_train) > 20:
        try:
            min_class_count = min(y_train.value_counts().values)
            k_neighbors = min(5, min_class_count - 1) if min_class_count > 1 else 1
            smote = SMOTE(random_state=random_state, k_neighbors=k_neighbors)
            X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train)
        except Exception:
            # If SMOTE fails, use class weights instead
            pass
    
    models_config = {}
    all_metrics = {}
    model_objects = {}
    
    # ====================================================
    # Model 1: Logistic Regression
    # ====================================================
    lr_model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=random_state,
        C=1.0,
    )
    lr_model.fit(X_train_resampled, y_train_resampled)
    
    lr_pred_proba = lr_model.predict_proba(X_test_scaled)[:, 1]
    lr_metrics = _evaluate_model(y_test, lr_pred_proba, "Logistic Regression")
    lr_metrics["model_type"] = "logistic_regression"
    all_metrics["logistic_regression"] = lr_metrics
    model_objects["logistic_regression"] = {
        "model": lr_model,
        "preprocessor": scaler,
        "features": feature_columns,
    }
    
    # ====================================================
    # Model 2: Random Forest
    # ====================================================
    rf_model = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    rf_model.fit(X_train_resampled, y_train_resampled)
    
    rf_pred_proba = rf_model.predict_proba(X_test_scaled)[:, 1]
    rf_metrics = _evaluate_model(y_test, rf_pred_proba, "Random Forest")
    rf_metrics["model_type"] = "random_forest"
    all_metrics["random_forest"] = rf_metrics
    model_objects["random_forest"] = {
        "model": rf_model,
        "preprocessor": scaler,
        "features": feature_columns,
    }
    
    # Feature importance from Random Forest
    rf_importance = dict(zip(feature_columns, rf_model.feature_importances_.tolist()))
    
    # ====================================================
    # Model 3: XGBoost
    # ====================================================
    if HAS_XGB:
        scale_pos_weight = (y_train_resampled == 0).sum() / max((y_train_resampled == 1).sum(), 1)
        xgb_model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            scale_pos_weight=scale_pos_weight,
            random_state=random_state,
            eval_metric="aucpr",
            use_label_encoder=False,
            n_jobs=-1,
        )
        xgb_model.fit(X_train_resampled, y_train_resampled)
        
        xgb_pred_proba = xgb_model.predict_proba(X_test_scaled)[:, 1]
        xgb_metrics = _evaluate_model(y_test, xgb_pred_proba, "XGBoost")
        xgb_metrics["model_type"] = "xgboost"
        all_metrics["xgboost"] = xgb_metrics
        model_objects["xgboost"] = {
            "model": xgb_model,
            "preprocessor": scaler,
            "features": feature_columns,
        }
        
        # XGBoost feature importance
        xgb_importance = dict(zip(feature_columns, xgb_model.feature_importances_.tolist()))
    
    # ====================================================
    # Threshold Optimization for best model
    # ====================================================
    # Find best model by F1
    best_model_name = max(all_metrics, key=lambda k: all_metrics[k]["f1"])
    best_proba = {
        "logistic_regression": lr_pred_proba,
        "random_forest": rf_pred_proba,
    }
    if HAS_XGB:
        best_proba["xgboost"] = xgb_pred_proba
    
    threshold_results = _optimize_thresholds(y_test, best_proba[best_model_name])
    
    # Select optimal threshold (maximizing F1 while keeping recall >= 0.5)
    optimal_threshold = 0.5
    for tr in sorted(threshold_results, key=lambda x: x["f1"], reverse=True):
        if tr["recall"] >= 0.5:
            optimal_threshold = tr["threshold"]
            break
    
    # ====================================================
    # Save models
    # ====================================================
    version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    version_dir = os.path.join(model_dir, version)
    os.makedirs(version_dir, exist_ok=True)
    
    # Save all models
    for name, mobj in model_objects.items():
        joblib.dump(mobj["model"], os.path.join(version_dir, f"{name}_model.joblib"))
    joblib.dump(scaler, os.path.join(version_dir, "preprocessor.joblib"))
    joblib.dump(feature_columns, os.path.join(version_dir, "features.joblib"))
    
    # Save metrics
    metrics_json = {
        "models": all_metrics,
        "best_model": best_model_name,
        "optimal_threshold": optimal_threshold,
        "threshold_analysis": threshold_results,
        "feature_importance_rf": rf_importance,
        "feature_importance_xgb": xgb_importance if HAS_XGB else {},
        "test_size": len(X_test),
        "train_size": len(X_train),
        "n_features": len(feature_columns),
        "class_distribution": {
            "train_fraud": int(y_train.sum()),
            "train_genuine": int((y_train == 0).sum()),
            "test_fraud": int(y_test.sum()),
            "test_genuine": int((y_test == 0).sum()),
        },
        "training_date": datetime.now().isoformat(),
        "version": version,
    }
    
    with open(os.path.join(version_dir, "metrics.json"), "w") as f:
        json.dump(metrics_json, f, indent=2, default=str)
    
    # Save metadata
    metadata = {
        "version": version,
        "feature_columns": feature_columns,
        "model_names": list(model_objects.keys()),
        "best_model": best_model_name,
        "optimal_threshold": optimal_threshold,
        "target_column": target_column,
    }
    with open(os.path.join(version_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Save test data for SHAP
    test_data["X_test_df"] = X_test
    joblib.dump(test_data, os.path.join(version_dir, "test_data.joblib"))
    
    # ====================================================
    # ROC and PR curve data
    # ====================================================
    for name in all_metrics:
        proba = best_proba.get(name, lr_pred_proba)
        fpr, tpr, _ = roc_curve(y_test, proba)
        precision_arr, recall_arr, _ = precision_recall_curve(y_test, proba)
        
        # Subsample for storage
        step = max(1, len(fpr) // 100)
        all_metrics[name]["roc_curve"] = {
            "fpr": fpr[::step].tolist(),
            "tpr": tpr[::step].tolist(),
        }
        step = max(1, len(precision_arr) // 100)
        all_metrics[name]["pr_curve"] = {
            "precision": precision_arr[::step].tolist(),
            "recall": recall_arr[::step].tolist(),
        }
    
    return {
        "version": version,
        "models_trained": list(model_objects.keys()),
        "metrics": all_metrics,
        "best_model": best_model_name,
        "optimal_threshold": optimal_threshold,
        "threshold_results": threshold_results,
        "feature_columns": feature_columns,
        "test_data": test_data,
        "model_dir": version_dir,
    }


def _evaluate_model(
    y_true: pd.Series,
    y_pred_proba: np.ndarray,
    model_name: str,
) -> Dict[str, Any]:
    """Evaluate a model and return comprehensive metrics."""
    # Default threshold
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    try:
        roc_auc = roc_auc_score(y_true, y_pred_proba)
    except ValueError:
        roc_auc = 0.0
    
    try:
        pr_auc = average_precision_score(y_true, y_pred_proba)
    except ValueError:
        pr_auc = 0.0
    
    cm = confusion_matrix(y_true, y_pred)
    
    return {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "confusion_matrix": cm.tolist(),
        "support": {
            "true": int(cm[1, 1] + cm[1, 0]) if cm.shape[0] > 1 else 0,
            "false": int(cm[0, 1] + cm[0, 0]) if cm.shape[0] > 1 else 0,
        },
    }


def _optimize_thresholds(
    y_true: pd.Series,
    y_pred_proba: np.ndarray,
    thresholds: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """Evaluate multiple classification thresholds."""
    if thresholds is None:
        thresholds = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]
    
    results = []
    for t in thresholds:
        y_pred = (y_pred_proba >= t).astype(int)
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        flagged = int(y_pred.sum())
        
        results.append({
            "threshold": round(t, 2),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1": round(float(f1), 4),
            "flagged_count": flagged,
        })
    
    return results


def load_model(model_dir: str, model_name: str = "xgboost") -> Optional[Dict[str, Any]]:
    """Load a trained model from disk."""
    try:
        model_path = os.path.join(model_dir, f"{model_name}_model.joblib")
        preprocessor_path = os.path.join(model_dir, "preprocessor.joblib")
        features_path = os.path.join(model_dir, "features.joblib")
        
        if not os.path.exists(model_path):
            # Try random_forest as fallback
            model_path = os.path.join(model_dir, "random_forest_model.joblib")
            if not os.path.exists(model_path):
                model_path = os.path.join(model_dir, "logistic_regression_model.joblib")
                if not os.path.exists(model_path):
                    return None
        
        return {
            "model": joblib.load(model_path),
            "preprocessor": joblib.load(preprocessor_path),
            "features": joblib.load(features_path),
        }
    except Exception:
        return None


def load_model_version(model_dir: str) -> Optional[Dict[str, Any]]:
    """Load the latest model version."""
    metadata_path = os.path.join(model_dir, "metadata.json")
    metrics_path = os.path.join(model_dir, "metrics.json")
    
    if not os.path.exists(metadata_path):
        return None
    
    with open(metadata_path) as f:
        metadata = json.load(f)
    
    metrics = {}
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            metrics = json.load(f)
    
    return {
        "metadata": metadata,
        "metrics": metrics,
        "dir": model_dir,
    }


def predict_transaction(
    features: Dict[str, float],
    model_object: Dict[str, Any],
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Predict fraud probability for a single transaction."""
    model = model_object["model"]
    preprocessor = model_object["preprocessor"]
    feature_columns = model_object["features"]
    
    # Build feature vector
    X = np.array([[features.get(col, 0) for col in feature_columns]])
    X = np.nan_to_num(X, nan=0, posinf=0, neginf=0)
    
    # Scale
    X_scaled = preprocessor.transform(X)
    
    # Predict
    proba = model.predict_proba(X_scaled)[0]
    fraud_prob = float(proba[1])
    prediction = "FRAUD" if fraud_prob >= threshold else "GENUINE"
    
    return {
        "fraud_probability": round(fraud_prob, 4),
        "prediction": prediction,
        "probabilities": {"genuine": round(float(proba[0]), 4), "fraud": round(fraud_prob, 4)},
    }
