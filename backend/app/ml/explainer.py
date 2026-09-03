"""SHAP-based model explainability.

Uses model_builtin importance (never crashes) for global explanations.
Attempts SHAP in a subprocess for individual explanations to prevent segfaults.
"""
from __future__ import annotations

import os
import json
import pickle
import tempfile
import logging
import subprocess
import sys
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

logger = logging.getLogger(__name__)


def compute_global_explanation(
    model: Any,
    X_background: pd.DataFrame,
    feature_columns: List[str],
    n_samples: int = 100,
) -> Dict[str, Any]:
    """Compute global feature importance. Uses model_builtin (safe) — no SHAP."""
    return _fallback_importance(model, feature_columns)


def explain_transaction(
    model: Any,
    X_single: pd.DataFrame,
    feature_columns: List[str],
    preprocessor: Any = None,
) -> Dict[str, Any]:
    """Explain a single transaction. Attempts SHAP in subprocess, falls back to builtin."""
    X_input = X_single[feature_columns].copy() if isinstance(X_single, pd.DataFrame) else X_single
    X_input = X_input.replace([np.inf, -np.inf], np.nan).fillna(0)

    if HAS_SHAP:
        result = _try_shap_subprocess(model, X_input, feature_columns)
        if result and result.get("method") == "shap":
            return result

    return _fallback_explanation(X_input, feature_columns)


def _try_shap_subprocess(model: Any, X_input: pd.DataFrame, feature_columns: List[str]) -> Optional[Dict[str, Any]]:
    """Try SHAP in a subprocess to prevent segfaults from crashing the server."""
    model_path = data_path = cols_path = result_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            model_path = f.name
            pickle.dump(model, f)
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            data_path = f.name
            pickle.dump(X_input, f)
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            cols_path = f.name
            pickle.dump(feature_columns, f)
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            result_path = f.name

        script = f"""
import pickle, json, os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
try:
    import shap, numpy as np
    with open(r'{model_path}', 'rb') as f: model = pickle.load(f)
    with open(r'{data_path}', 'rb') as f: X_input = pickle.load(f)
    with open(r'{cols_path}', 'rb') as f: feature_columns = pickle.load(f)
    model_type = type(model).__name__
    if model_type in ('XGBClassifier', 'RandomForestClassifier'):
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_input)
    else:
        explainer = shap.LinearExplainer(model, X_input.head(min(50, len(X_input))))
        shap_values = explainer.shap_values(X_input)
    if isinstance(shap_values, list): shap_values = shap_values[1]
    sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values
    contributions = []
    for i, feat in enumerate(feature_columns):
        contributions.append({{
            'feature': feat,
            'value': float(X_input.iloc[0, i]) if len(X_input) > 0 else 0,
            'shap_value': round(float(sv[i]), 6),
            'direction': 'positive' if sv[i] > 0 else 'negative',
        }})
    contributions.sort(key=lambda x: abs(x['shap_value']), reverse=True)
    explanation_text = []
    for c in contributions[:5]:
        if abs(c['shap_value']) > 0.001:
            d = 'increases' if c['direction'] == 'positive' else 'decreases'
            explanation_text.append(f"{{c['feature']}} ({{c['value']:.2f}}) {{d}} fraud risk by {{abs(c['shap_value']):.4f}}")
    result = {{
        'method': 'shap',
        'contributions': contributions[:20],
        'explanation_text': explanation_text,
        'base_value': round(float(explainer.expected_value[1] if isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value), 6),
    }}
    with open(r'{result_path}', 'w') as f: json.dump(result, f)
except Exception as e:
    with open(r'{result_path}', 'w') as f: json.dump({{'error': str(e), 'method': 'none'}}, f)
"""
        proc = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True, text=True, timeout=30,
        )

        if os.path.exists(result_path):
            with open(result_path, 'r') as f:
                result = json.load(f)
            return result
        return None
    except Exception as e:
        logger.warning(f"SHAP subprocess failed: {e}")
        return None
    finally:
        for p in [model_path, data_path, cols_path, result_path]:
            if p:
                try: os.unlink(p)
                except: pass


def _get_top_shap_features(
    shap_values: np.ndarray,
    feature_columns: List[str], positive: bool = True, top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Get top features with positive or negative SHAP contribution."""
    mean_shap = shap_values.mean(axis=0)
    indices = np.argsort(mean_shap)[::-1][:top_n] if positive else np.argsort(mean_shap)[:top_n]
    result = []
    for idx in indices:
        if idx < len(feature_columns):
            result.append({
                "feature": feature_columns[idx],
                "mean_shap": round(float(mean_shap[idx]), 6),
            })
    return result


def _fallback_importance(model: Any, feature_columns: List[str]) -> Dict[str, Any]:
    """Fallback feature importance using model's built-in importance."""
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
            "features": [
                {"feature": name, "importance": round(float(imp), 6)}
                for name, imp in sorted_imp[:30]
            ],
        }
    return {
        "method": "none",
        "features": [{"feature": f, "importance": 0.0} for f in feature_columns[:20]],
    }


def _fallback_explanation(
    X_input: pd.DataFrame, feature_columns: List[str], error: Optional[str] = None,
) -> Dict[str, Any]:
    """Fallback explanation using feature values."""
    contributions = []
    for i, feat in enumerate(feature_columns):
        val = float(X_input.iloc[0, i]) if len(X_input) > 0 and i < X_input.shape[1] else 0
        contributions.append({
            "feature": feat,
            "value": val,
            "shap_value": 0.0,
            "direction": "unknown",
        })
    return {
        "method": "builtin",
        "contributions": contributions[:20],
        "explanation_text": ["Using model feature values for reference. SHAP was unavailable."],
        "error": error,
    }
