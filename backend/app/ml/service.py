"""ML Service — user-scoped singleton managing per-user ML pipelines."""
from __future__ import annotations

import os
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.ml.schema_detector import detect_schema, detect_target_column
from app.ml.data_profiler import profile_dataset, clean_dataset, generate_eda_data
from app.ml.feature_engineering import build_feature_engineering_pipeline
from app.ml.model_trainer import (
    train_models, load_model, load_model_version, predict_transaction,
)
from app.ml.anomaly_detector import train_anomaly_detector, score_anomalies, score_single_transaction
from app.ml.risk_engine import compute_risk_score
from app.ml.explainer import compute_global_explanation, explain_transaction

logger = logging.getLogger(__name__)
settings = get_settings()


def _fallback_feature_importance(model, feature_columns):
    """Fallback feature importance using model's built-in attributes."""
    importance = None
    if hasattr(model, "feature_importances_"):
        importance = model.feature_importances_
    elif hasattr(model, "coef_"):
        importance = np.abs(model.coef_[0]) if model.coef_.ndim > 1 else np.abs(model.coef_)

    if importance is not None:
        sorted_imp = sorted(
            zip(feature_columns, importance.tolist()),
            key=lambda x: x[1], reverse=True,
        )
        return {
            "method": "model_builtin",
            "features": [{"feature": n, "importance": round(float(v), 6)} for n, v in sorted_imp[:30]],
        }
    return {"method": "none", "features": [{"feature": f, "importance": 0.0} for f in feature_columns[:20]]}


class UserMLWorkspace:
    """Per-user ML workspace holding datasets, models, and training state."""

    def __init__(self):
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.model_version: Optional[str] = None
        self.model_objects: Dict[str, Any] = {}
        self.anomaly_object: Optional[Dict[str, Any]] = None
        self.feature_columns: List[str] = []
        self.feature_docs: Dict[str, str] = {}
        self.threshold: float = 0.5
        self.metrics: Dict[str, Any] = {}
        self.global_explanation: Optional[Dict[str, Any]] = None
        self.test_data: Optional[Dict[str, Any]] = None
        self.target_column: Optional[str] = None
        self.training_results: Optional[Dict[str, Any]] = None
        self.eda_data: Optional[Dict[str, Any]] = None
        self.dataset_id: Optional[str] = None  # active dataset

    def get_model_info(self) -> Dict[str, Any]:
        models_info = []
        for name in ["logistic_regression", "random_forest", "xgboost"]:
            if name in self.metrics:
                m = self.metrics[name]
                models_info.append({
                    "model_name": name,
                    "version": self.model_version or "unknown",
                    "metrics": {
                        "precision": m.get("precision", 0),
                        "recall": m.get("recall", 0),
                        "f1": m.get("f1", 0),
                        "pr_auc": m.get("pr_auc", 0),
                        "roc_auc": m.get("roc_auc", 0),
                    },
                    "threshold": self.threshold,
                    "has_model": name in self.model_objects,
                    "features_used": self.feature_columns,
                })
        return {
            "models": models_info,
            "version": self.model_version,
            "threshold": self.threshold,
            "n_features": len(self.feature_columns),
            "target_column": self.target_column,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "models_loaded": len(self.model_objects),
            "model_version": self.model_version,
            "threshold": self.threshold,
            "n_features": len(self.feature_columns),
            "has_anomaly_detector": self.anomaly_object is not None,
            "has_training_data": bool(self.test_data),
            "target_column": self.target_column,
            "has_dataset": bool(self.datasets),
            "dataset_id": self.dataset_id,
        }


class MLService:
    """Central ML service — manages per-user workspaces."""

    def __init__(self):
        self._workspaces: Dict[str, UserMLWorkspace] = {}  # user_id -> workspace
        self._load_global_models()  # Load models from disk as fallback

    def _load_global_models(self):
        """Try to load the latest trained model from disk."""
        models_dir = settings.MODELS_DIR
        if not os.path.exists(models_dir):
            os.makedirs(models_dir, exist_ok=True)
            return

        versions = sorted(
            [d for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d))],
            reverse=True,
        )
        if not versions:
            return

        latest = os.path.join(models_dir, versions[0])
        try:
            self._global_model_objects = {}
            for model_name in ["xgboost", "random_forest", "logistic_regression"]:
                mobj = load_model(latest, model_name)
                if mobj:
                    self._global_model_objects[model_name] = mobj
            meta = load_model_version(latest)
            if meta:
                self._global_model_version = meta["metadata"]["version"]
                self._global_feature_columns = meta["metadata"]["feature_columns"]
                self._global_threshold = meta["metadata"].get("optimal_threshold", 0.5)
                self._global_metrics = meta["metrics"].get("models", {})
                self._global_target_column = meta["metadata"].get("target_column")
                anomaly_path = os.path.join(latest, "anomaly_model.joblib")
                if os.path.exists(anomaly_path):
                    import joblib
                    self._global_anomaly_object = {
                        "model": joblib.load(anomaly_path),
                        "scaler": joblib.load(os.path.join(latest, "anomaly_scaler.joblib")),
                        "features": self._global_feature_columns,
                    }
                else:
                    self._global_anomaly_object = None
            else:
                self._global_model_version = None
                self._global_feature_columns = []
                self._global_threshold = 0.5
                self._global_metrics = {}
                self._global_target_column = None
                self._global_anomaly_object = None
        except Exception as e:
            logger.warning(f"Could not load global model: {e}")
            self._global_model_objects = {}
            self._global_model_version = None
            self._global_feature_columns = []
            self._global_threshold = 0.5
            self._global_metrics = {}
            self._global_target_column = None
            self._global_anomaly_object = None

    def get_workspace(self, user_id: str) -> UserMLWorkspace:
        """Get or create a user's ML workspace."""
        if user_id not in self._workspaces:
            ws = UserMLWorkspace()
            # If user has no trained models, fall back to global
            if not ws.model_objects:
                ws.model_objects = getattr(self, '_global_model_objects', {})
                ws.model_version = getattr(self, '_global_model_version', None)
                ws.feature_columns = getattr(self, '_global_feature_columns', [])
                ws.threshold = getattr(self, '_global_threshold', 0.5)
                ws.metrics = getattr(self, '_global_metrics', {})
                ws.target_column = getattr(self, '_global_target_column', None)
                ws.anomaly_object = getattr(self, '_global_anomaly_object', None)
            self._workspaces[user_id] = ws
        return self._workspaces[user_id]

    def clear_workspace(self, user_id: str) -> None:
        """Clear a user's workspace (on logout or new analysis)."""
        if user_id in self._workspaces:
            del self._workspaces[user_id]

    # ========================================
    # Dataset Management (user-scoped)
    # ========================================

    def upload_dataset(self, user_id: str, df: pd.DataFrame, filename: str) -> Dict[str, Any]:
        ws = self.get_workspace(user_id)
        dataset_id = str(uuid.uuid4())[:8]

        column_map, schema_warnings = detect_schema(df)
        target_col = detect_target_column(df)
        if target_col:
            column_map["fraud_label"] = target_col

        profile = profile_dataset(df, column_map, filename)
        profile["warnings"].extend(schema_warnings)

        ws.datasets[dataset_id] = {
            "raw_df": df,
            "column_map": column_map,
            "profile": profile,
            "filename": filename,
            "cleaned_df": None,
        }
        ws.dataset_id = dataset_id

        return {
            "dataset_id": dataset_id,
            "profile": profile,
            "message": f"Dataset uploaded: {filename}",
        }

    def get_dataset(self, user_id: str, dataset_id: str) -> Optional[Dict[str, Any]]:
        ws = self.get_workspace(user_id)
        return ws.datasets.get(dataset_id)

    # ========================================
    # Training Pipeline (user-scoped)
    # ========================================

    def train(
        self,
        user_id: str,
        dataset_id: str,
        target_column: Optional[str] = None,
        test_size: float = 0.2,
        use_smote: bool = True,
    ) -> Dict[str, Any]:
        ws = self.get_workspace(user_id)
        dataset = ws.datasets.get(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found for user {user_id}")

        df = dataset["raw_df"].copy()
        column_map = dataset["column_map"]

        if target_column:
            column_map["fraud_label"] = target_column
            ws.target_column = target_column
        else:
            ws.target_column = column_map.get("fraud_label")

        df, cleaning_actions = clean_dataset(df, column_map)
        dataset["cleaned_df"] = df

        ws.eda_data = generate_eda_data(df, column_map)

        df, ws.feature_columns, ws.feature_docs = build_feature_engineering_pipeline(df, column_map)

        has_label = ws.target_column and ws.target_column in df.columns

        results = {
            "has_fraud_label": has_label,
            "cleaning_actions": cleaning_actions,
            "n_features": len(ws.feature_columns),
        }

        if has_label:
            model_dir = os.path.join(settings.MODELS_DIR, f"user_{user_id[:8]}")
            os.makedirs(model_dir, exist_ok=True)

            train_results = train_models(
                df, ws.feature_columns, ws.target_column,
                model_dir=model_dir,
                test_size=test_size,
                use_smote=use_smote,
            )
            ws.model_version = train_results["version"]
            ws.metrics = train_results["metrics"]
            ws.threshold = train_results["optimal_threshold"]
            ws.test_data = train_results["test_data"]
            ws.training_results = train_results

            for name in train_results["models_trained"]:
                mobj = load_model(model_dir, name)
                if mobj:
                    ws.model_objects[name] = mobj

            results["models_trained"] = train_results["models_trained"]
            results["metrics"] = train_results["metrics"]
            results["best_model"] = train_results["best_model"]
            results["optimal_threshold"] = train_results["optimal_threshold"]
            results["threshold_results"] = train_results["threshold_results"]

            anomaly_result = train_anomaly_detector(
                df, ws.feature_columns, model_dir, contamination=0.05,
            )
            ws.anomaly_object = anomaly_result

            if ws.model_objects and ws.test_data:
                best_model_name = train_results["best_model"]
                if best_model_name in ws.model_objects:
                    model_obj = ws.model_objects[best_model_name]
                    X_test = ws.test_data.get("X_test_df", ws.test_data.get("X_test"))
                    if X_test is not None and len(X_test) > 0:
                        if not isinstance(X_test, pd.DataFrame):
                            X_test = pd.DataFrame(X_test, columns=ws.feature_columns)
                        try:
                            ws.global_explanation = compute_global_explanation(
                                model_obj["model"], X_test.head(100), ws.feature_columns,
                            )
                        except Exception as e:
                            logger.warning(f"SHAP global explanation failed: {e}")
                            ws.global_explanation = _fallback_feature_importance(model_obj["model"], ws.feature_columns)

            df = score_anomalies(df, ws.feature_columns, ws.anomaly_object)
        else:
            model_dir = os.path.join(settings.MODELS_DIR, f"user_{user_id[:8]}", "anomaly_only")
            os.makedirs(model_dir, exist_ok=True)
            ws.anomaly_object = train_anomaly_detector(
                df, ws.feature_columns, model_dir, contamination=0.05,
            )
            df = score_anomalies(df, ws.feature_columns, ws.anomaly_object)
            results["models_trained"] = ["anomaly_detection"]
            results["message"] = "No fraud label detected. Operating in anomaly-detection mode."

        results["n_transactions"] = len(df)
        results["version"] = ws.model_version
        return results

    # ========================================
    # Prediction (user-scoped)
    # ========================================

    def predict_single(self, user_id: str, transaction: Dict[str, Any]) -> Dict[str, Any]:
        ws = self.get_workspace(user_id)
        if not ws.model_objects:
            return self._empty_prediction()

        best_model_name = self._get_best_model_name(ws)
        model_obj = ws.model_objects.get(best_model_name)
        if not model_obj:
            return self._empty_prediction()

        features = self._extract_features(ws, transaction)
        pred = predict_transaction(features, model_obj, ws.threshold)

        anomaly_score = 0.5
        if ws.anomaly_object:
            anomaly_score = score_single_transaction(features, ws.feature_columns, ws.anomaly_object)

        risk = compute_risk_score(pred["fraud_probability"], anomaly_score, features)

        return {
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())[:12]),
            "fraud_probability": pred["fraud_probability"],
            "prediction": pred["prediction"],
            "anomaly_score": anomaly_score,
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "reasons": risk["reasons"],
            "model_version": ws.model_version,
            "components": risk["components"],
            "timestamp": datetime.utcnow().isoformat(),
            "features": features,  # Include feature vector for persistence
        }

    def _extract_features(self, ws: UserMLWorkspace, transaction: Dict[str, Any]) -> Dict[str, float]:
        features = {}
        for col in ws.feature_columns:
            val = transaction.get(col)
            if val is None:
                features[col] = 0.0
            else:
                try:
                    features[col] = float(val)
                except (ValueError, TypeError):
                    features[col] = 0.0
        return features

    def _get_best_model_name(self, ws: UserMLWorkspace) -> str:
        priority = ["xgboost", "random_forest", "logistic_regression"]
        for name in priority:
            if name in ws.model_objects:
                return name
        return list(ws.model_objects.keys())[0] if ws.model_objects else "unknown"

    def _empty_prediction(self) -> Dict[str, Any]:
        return {
            "transaction_id": str(uuid.uuid4())[:12],
            "fraud_probability": 0.0,
            "prediction": "UNKNOWN",
            "anomaly_score": 0.5,
            "risk_score": 0,
            "risk_level": "LOW",
            "reasons": ["No trained model available"],
            "model_version": None,
            "components": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ========================================
    # Model Info (user-scoped)
    # ========================================

    def get_model_info(self, user_id: str) -> Dict[str, Any]:
        ws = self.get_workspace(user_id)
        return ws.get_model_info()

    def get_comparison(self, user_id: str) -> List[Dict[str, Any]]:
        return self.get_model_info(user_id).get("models", [])

    def get_threshold_analysis(self, user_id: str) -> List[Dict[str, Any]]:
        ws = self.get_workspace(user_id)
        if ws.training_results and "threshold_results" in ws.training_results:
            return ws.training_results["threshold_results"]
        return []

    def get_global_explanation(self, user_id: str) -> Optional[Dict[str, Any]]:
        ws = self.get_workspace(user_id)
        return ws.global_explanation

    def compute_global_explanation_on_demand(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Compute global SHAP explanation on demand if not cached. Uses training data."""
        ws = self.get_workspace(user_id)
        if not ws.model_objects or not ws.feature_columns:
            return None
        # Need training data to compute global SHAP
        train_data = None
        for did, data in ws.datasets.items():
            if data.get("cleaned_df") is not None:
                train_data = data["cleaned_df"]
                break
        if train_data is None:
            return None
        best_name = self._get_best_model_name(ws)
        model_obj = ws.model_objects[best_name]
        try:
            # Use model_builtin importance (never crashes)
            from app.ml.explainer import _fallback_importance
            explanation = _fallback_importance(model_obj["model"], ws.feature_columns)
            if explanation and explanation.get("features"):
                ws.global_explanation = explanation
                return explanation
        except Exception as e:
            logger.warning(f"Failed to compute global explanation: {e}")
        return None

    def explain_transaction_by_id(self, user_id: str, transaction_id: str, features: Dict[str, Any]) -> Dict[str, Any]:
        ws = self.get_workspace(user_id)
        if not ws.model_objects or not ws.feature_columns:
            return {"method": "none", "contributions": [], "explanation_text": ["No model available"]}

        best_name = self._get_best_model_name(ws)
        model_obj = ws.model_objects[best_name]

        feat_vec = pd.DataFrame([{col: features.get(col, 0) for col in ws.feature_columns}])

        return explain_transaction(
            model_obj["model"], feat_vec, ws.feature_columns, model_obj.get("preprocessor"),
        )

    def get_eda_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        ws = self.get_workspace(user_id)
        return ws.eda_data

    def get_global_status(self) -> Dict[str, Any]:
        """Get global status for health endpoint."""
        return {
            "models_loaded": len(getattr(self, '_global_model_objects', {})),
            "model_version": getattr(self, '_global_model_version', None),
            "threshold": getattr(self, '_global_threshold', 0.5),
            "n_features": len(getattr(self, '_global_feature_columns', [])),
            "has_anomaly_detector": getattr(self, '_global_anomaly_object', None) is not None,
            "has_training_data": False,
            "target_column": getattr(self, '_global_target_column', None),
            "has_dataset": False,
            "dataset_id": None,
        }

    def get_status(self, user_id: str) -> Dict[str, Any]:
        ws = self.get_workspace(user_id)
        return ws.get_status()

    # ========================================
    # Feature importance (user-scoped)
    # ========================================

    def get_feature_importance(self, user_id: str) -> Dict[str, Any]:
        ws = self.get_workspace(user_id)
        if ws.global_explanation and ws.global_explanation.get("features"):
            return ws.global_explanation
        # Fallback: build from model internals
        if ws.model_objects:
            best = self._get_best_model_name(ws)
            model_obj = ws.model_objects.get(best)
            if model_obj and hasattr(model_obj["model"], "feature_importances_"):
                importances = model_obj["model"].feature_importances_
                features = [{"feature": col, "importance": float(imp)}
                           for col, imp in zip(ws.feature_columns, importances)]
                features.sort(key=lambda x: x["importance"], reverse=True)
                return {"features": features[:20], "method": "tree_importance"}
        return {"features": [], "method": "none"}


# Singleton
ml_service = MLService()
