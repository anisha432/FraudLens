"""Tests for the Fraud Detection ML Pipeline."""
import os
import sys
import json
import tempfile
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.schema_detector import detect_schema, detect_target_column, get_column_types
from app.ml.data_profiler import profile_dataset, clean_dataset, generate_eda_data
from app.ml.feature_engineering import build_feature_engineering_pipeline
from app.ml.model_trainer import train_models, predict_transaction, load_model, _optimize_thresholds
from app.ml.anomaly_detector import train_anomaly_detector, score_anomalies, score_single_transaction
from app.ml.risk_engine import compute_risk_score, _get_risk_level, get_alert_severity
from app.ml.demo_data import generate_demo_dataset, generate_minimal_dataset


# ========================================
# Schema Detection Tests
# ========================================

class TestSchemaDetection:
    def test_detect_fraud_label(self):
        df = pd.DataFrame({"amount": [100, 200], "is_fraud": [0, 1]})
        col_map, _ = detect_schema(df)
        assert col_map.get("fraud_label") == "is_fraud"

    def test_detect_amount_column(self):
        df = pd.DataFrame({"transaction_amount": [100, 200], "name": ["a", "b"]})
        col_map, _ = detect_schema(df)
        assert col_map.get("amount") == "transaction_amount"

    def test_flexible_column_names(self):
        for col_name in ["Amount", "AMOUNT", "transaction_amount", "txn_amount", "amt", "value"]:
            df = pd.DataFrame({col_name: [100, 200], "other": ["a", "b"]})
            col_map, _ = detect_schema(df)
            assert col_map.get("amount") == col_name, f"Failed for {col_name}"

    def test_no_amount_column(self):
        df = pd.DataFrame({"name": ["a", "b"], "category": ["x", "y"]})
        col_map, warnings = detect_schema(df)
        # No numeric columns means no fallback amount detection
        # but the system should not crash

    def test_detect_target_string_labels(self):
        df = pd.DataFrame({"amount": [100, 200, 300], "label": ["fraud", "legitimate", "fraud"]})
        target = detect_target_column(df)
        assert target == "label"

    def test_detect_target_numeric_labels(self):
        df = pd.DataFrame({"amount": [100, 200, 300], "class": [0, 1, 0]})
        target = detect_target_column(df)
        assert target == "class"

    def test_no_target_column(self):
        df = pd.DataFrame({"amount": [100, 200], "merchant": ["a", "b"]})
        target = detect_target_column(df)
        assert target is None

    def test_column_types(self):
        df = pd.DataFrame({
            "amount": list(range(100)),
            "is_fraud": [0, 1] * 50,
            "category": ["a", "b", "c"] * 33 + ["a"],
            "date": pd.to_datetime(["2024-01-01"] * 100),
        })
        types = get_column_types(df)
        assert "amount" in types["numerical"]  # > 20 unique values
        assert "date" in types["date"]


# ========================================
# Data Profiling Tests
# ========================================

class TestDataProfiling:
    def test_profile_basic(self):
        df = pd.DataFrame({
            "amount": [100, 200, 300],
            "is_fraud": [0, 1, 0],
            "merchant": ["a", "b", "c"],
        })
        col_map = {"amount": "amount", "fraud_label": "is_fraud"}
        profile = profile_dataset(df, col_map, "test.csv")
        assert profile["row_count"] == 3
        assert profile["column_count"] == 3
        assert profile["has_fraud_label"] is True
        assert profile["quality_score"] > 0

    def test_profile_quality_score_drops_for_small_data(self):
        df = pd.DataFrame({"amount": [100, 200]})
        profile = profile_dataset(df, {"amount": "amount"}, "small.csv")
        assert profile["quality_score"] < 100

    def test_profile_missing_label_warning(self):
        df = pd.DataFrame({"amount": list(range(500))})
        profile = profile_dataset(df, {"amount": "amount"}, "nolabel.csv")
        assert any("anomaly-detection" in w.lower() for w in profile["warnings"])


# ========================================
# Data Cleaning Tests
# ========================================

class TestDataCleaning:
    def test_clean_removes_duplicates(self):
        df = pd.DataFrame({"amount": [100, 200, 300], "cat": ["a", "b", "c"]})
        # Add exact duplicate rows
        df = pd.concat([df, df.iloc[:2]], ignore_index=True)
        assert len(df) == 5
        cleaned, actions = clean_dataset(df, {"amount": "amount"})
        assert len(cleaned) == 3

    def test_clean_handles_missing_amounts(self):
        df = pd.DataFrame({"amount": [100, None, 300], "cat": ["a", "b", "c"]})
        cleaned, actions = clean_dataset(df, {"amount": "amount"})
        assert cleaned["amount"].isnull().sum() == 0

    def test_clean_maps_string_labels(self):
        df = pd.DataFrame({"amount": [100, 200], "fraud": ["yes", "no"]})
        cleaned, _ = clean_dataset(df, {"amount": "amount", "fraud_label": "fraud"})
        assert set(cleaned["fraud"].unique()).issubset({0, 1})


# ========================================
# Feature Engineering Tests
# ========================================

class TestFeatureEngineering:
    def test_generates_features(self):
        df = generate_demo_dataset(200)
        df, features, docs = build_feature_engineering_pipeline(df, {
            "amount": "amount", "timestamp": "timestamp",
            "user_id": "user_id", "merchant": "merchant",
        })
        assert len(features) > 10
        assert "amount" in features
        assert "log_amount" in features
        assert "hour" in features
        assert "is_weekend" in features

    def test_no_categorical_crash(self):
        df = pd.DataFrame({
            "amount": [100, 200, 300],
            "tx_id": ["T1", "T2", "T3"],
        })
        df, features, _ = build_feature_engineering_pipeline(df, {"amount": "amount"})
        assert len(features) > 0


# ========================================
# Model Training Tests
# ========================================

class TestModelTraining:
    @pytest.fixture
    def trained_models(self, tmp_path):
        df = generate_demo_dataset(500)
        column_map = {"amount": "amount", "timestamp": "timestamp",
                       "user_id": "user_id", "merchant": "merchant",
                       "fraud_label": "fraud"}
        df, _ = clean_dataset(df, column_map)
        df, features, _ = build_feature_engineering_pipeline(df, column_map)
        results = train_models(df, features, "fraud", model_dir=str(tmp_path), use_smote=False)
        return results

    def test_trains_all_models(self, trained_models):
        assert "logistic_regression" in trained_models["models_trained"]
        assert "random_forest" in trained_models["models_trained"]
        assert "xgboost" in trained_models["models_trained"]

    def test_has_metrics(self, trained_models):
        for name in trained_models["models_trained"]:
            m = trained_models["metrics"][name]
            assert 0 <= m["precision"] <= 1
            assert 0 <= m["recall"] <= 1
            assert 0 <= m["f1"] <= 1
            assert 0 <= m["pr_auc"] <= 1
            assert 0 <= m["roc_auc"] <= 1

    def test_threshold_results(self, trained_models):
        assert len(trained_models["threshold_results"]) > 0
        for tr in trained_models["threshold_results"]:
            assert 0 <= tr["threshold"] <= 1

    def test_best_model_exists(self, trained_models):
        assert trained_models["best_model"] in trained_models["models_trained"]

    def test_predict_single(self, trained_models):
        features = {col: 0.0 for col in trained_models["feature_columns"][:5]}
        features["amount"] = 50000
        features["log_amount"] = np.log1p(50000)
        model_dir = trained_models["model_dir"]
        model_obj = load_model(model_dir, "xgboost")
        assert model_obj is not None
        result = predict_transaction(features, model_obj)
        assert 0 <= result["fraud_probability"] <= 1
        assert result["prediction"] in ("FRAUD", "GENUINE")

    def test_saves_artifacts(self, trained_models):
        model_dir = trained_models["model_dir"]
        assert os.path.exists(os.path.join(model_dir, "metrics.json"))
        assert os.path.exists(os.path.join(model_dir, "metadata.json"))
        assert os.path.exists(os.path.join(model_dir, "xgboost_model.joblib"))
        assert os.path.exists(os.path.join(model_dir, "preprocessor.joblib"))
        assert os.path.exists(os.path.join(model_dir, "features.joblib"))


# ========================================
# Threshold Optimization Tests
# ========================================

class TestThresholdOptimization:
    def test_threshold_range(self):
        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1])
        y_proba = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 0.5, 0.3])
        results = _optimize_thresholds(y_true, y_proba, [0.3, 0.5, 0.7])
        assert len(results) == 3
        for r in results:
            assert r["threshold"] in [0.3, 0.5, 0.7]


# ========================================
# Anomaly Detection Tests
# ========================================

class TestAnomalyDetection:
    def test_anomaly_scores(self, tmp_path):
        df = pd.DataFrame({
            "amount": np.concatenate([np.random.normal(100, 10, 100), [10000]]),
            "hour": np.random.randint(0, 24, 101),
        })
        features = ["amount", "hour"]
        model_obj = train_anomaly_detector(df, features, str(tmp_path))
        result = score_anomalies(df, features, model_obj)
        assert "anomaly_score" in result.columns
        assert "is_anomaly" in result.columns
        assert 0 <= result["anomaly_score"].min()
        assert result["anomaly_score"].max() <= 1

    def test_single_score(self, tmp_path):
        df = pd.DataFrame({"amount": np.random.normal(100, 10, 50), "hour": np.random.randint(0, 24, 50)})
        model_obj = train_anomaly_detector(df, ["amount", "hour"], str(tmp_path))
        score = score_single_transaction({"amount": 50, "hour": 14}, ["amount", "hour"], model_obj)
        assert 0 <= score <= 1


# ========================================
# Risk Engine Tests
# ========================================

class TestRiskEngine:
    def test_risk_levels(self):
        assert _get_risk_level(90) == "CRITICAL"
        assert _get_risk_level(70) == "HIGH"
        assert _get_risk_level(50) == "MEDIUM"
        assert _get_risk_level(10) == "LOW"

    def test_compute_risk_score(self):
        result = compute_risk_score(
            fraud_probability=0.9,
            anomaly_score=0.8,
            features={"user_spending_deviation": 3.5, "is_unusual_hour": 1, "is_new_device": 1},
        )
        assert 0 <= result["risk_score"] <= 100
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert len(result["reasons"]) > 0

    def test_low_risk(self):
        result = compute_risk_score(0.1, 0.2, {"user_spending_deviation": 0.5})
        assert result["risk_level"] in ("LOW", "MEDIUM")

    def test_alert_severity(self):
        assert get_alert_severity("CRITICAL") == "CRITICAL"
        assert get_alert_severity("HIGH") == "HIGH"
        assert get_alert_severity("LOW") == "LOW"


# ========================================
# Demo Data Tests
# ========================================

class TestDemoData:
    def test_generate_dataset(self):
        df = generate_demo_dataset(100)
        assert len(df) == 100
        assert "fraud" in df.columns
        assert "transaction_id" in df.columns
        assert "amount" in df.columns
        assert df["amount"].min() > 0

    def test_generate_minimal(self):
        df = generate_minimal_dataset(50)
        assert len(df) == 50
        assert "fraud" not in df.columns


# ========================================
# EDA Tests
# ========================================

class TestEDA:
    def test_generate_eda(self):
        df = generate_demo_dataset(200)
        column_map = {"amount": "amount", "timestamp": "timestamp", "fraud_label": "fraud"}
        eda = generate_eda_data(df, column_map)
        assert "summary" in eda
        assert "amount_stats" in eda
        assert "class_distribution" in eda
        assert eda["summary"]["total_transactions"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
