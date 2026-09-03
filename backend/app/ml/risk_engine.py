"""Hybrid Risk Intelligence Engine.

Combines supervised fraud probability, anomaly score, and behavioral indicators
into a unified risk score (0-100) with risk levels.

IMPORTANT: This is a decision-support score, NOT a guaranteed probability.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
import numpy as np


# Default weights — configurable
DEFAULT_WEIGHTS = {
    "fraud_probability": 0.50,  # Supervised model contribution
    "anomaly_score": 0.25,      # Anomaly detection contribution
    "behavioral_score": 0.25,   # Rule-based behavioral indicators
}

RISK_LEVELS = {
    "LOW": {"min": 0, "max": 29, "color": "#22c55e"},
    "MEDIUM": {"min": 30, "max": 59, "color": "#eab308"},
    "HIGH": {"min": 60, "max": 79, "color": "#f97316"},
    "CRITICAL": {"min": 80, "max": 100, "color": "#ef4444"},
}


def compute_risk_score(
    fraud_probability: float,
    anomaly_score: float,
    features: Optional[Dict[str, float]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Compute hybrid risk score combining multiple signals.
    
    Args:
        fraud_probability: Output from supervised model (0-1)
        anomaly_score: Output from anomaly detector (0-1)
        features: Feature dict for behavioral rule evaluation
        weights: Custom weights for score components
    
    Returns:
        Dict with risk_score, risk_level, reasons, behavioral_score
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    
    # Normalize weights
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}
    
    # Behavioral score from rules
    behavioral_score, behavioral_reasons = _evaluate_behavioral_rules(features or {})
    
    # Weighted combination
    risk_score = (
        fraud_probability * weights.get("fraud_probability", 0.5)
        + anomaly_score * weights.get("anomaly_score", 0.25)
        + behavioral_score * weights.get("behavioral_score", 0.25)
    )
    
    # Scale to 0-100
    risk_score = float(np.clip(risk_score * 100, 0, 100))
    risk_score = round(risk_score, 1)
    
    # Determine risk level
    risk_level = _get_risk_level(risk_score)
    
    # Generate reasons
    reasons = _generate_reasons(fraud_probability, anomaly_score, features or {})
    reasons.extend(behavioral_reasons)
    
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reasons": reasons,
        "behavioral_score": round(behavioral_score, 4),
        "components": {
            "fraud_probability": round(fraud_probability, 4),
            "anomaly_score": round(anomaly_score, 4),
            "behavioral_score": round(behavioral_score, 4),
        },
    }


def _evaluate_behavioral_rules(features: Dict[str, float]) -> tuple[float, List[str]]:
    """
    Evaluate behavioral rules to produce a risk indicator score.
    
    Each rule adds to the score. Returns (score, reasons).
    """
    score = 0.0
    reasons = []
    
    # High amount deviation
    amt_dev = features.get("user_spending_deviation", 0)
    if amt_dev > 3:
        score += 0.3
        reasons.append("Transaction amount significantly above user's normal spending")
    elif amt_dev > 2:
        score += 0.15
        reasons.append("Transaction amount above user's typical spending")
    
    # Unusual hour
    if features.get("is_unusual_hour", 0) == 1:
        score += 0.15
        reasons.append("Transaction at unusual time (11pm-5am)")
    
    # New device
    if features.get("is_new_device", 0) == 1:
        score += 0.2
        reasons.append("New/unrecognized device used")
    
    # High amount vs average
    amt_ratio = features.get("amount_vs_avg", 1)
    if amt_ratio > 5:
        score += 0.2
        reasons.append(f"Transaction amount is {amt_ratio:.1f}x above average")
    elif amt_ratio > 3:
        score += 0.1
        reasons.append(f"Transaction amount is {amt_ratio:.1f}x above average")
    
    # Unusual location (low frequency)
    loc_freq = features.get("location_frequency", 100)
    if loc_freq <= 2:
        score += 0.15
        reasons.append("Transaction from unusual/rare location")
    
    # High transaction velocity
    user_freq = features.get("user_tx_frequency", 1)
    if user_freq > 10:
        score += 0.15
        reasons.append("Abnormally high transaction frequency")
    
    # Weekend + high amount
    if features.get("is_weekend", 0) == 1 and amt_ratio > 2:
        score += 0.05
        reasons.append("High-value weekend transaction")
    
    return min(score, 1.0), reasons


def _get_risk_level(risk_score: float) -> str:
    """Determine risk level from score."""
    if risk_score >= 80:
        return "CRITICAL"
    elif risk_score >= 60:
        return "HIGH"
    elif risk_score >= 30:
        return "MEDIUM"
    else:
        return "LOW"


def _generate_reasons(
    fraud_prob: float,
    anomaly_score: float,
    features: Dict[str, float],
) -> List[str]:
    """Generate human-readable reasons for the risk score."""
    reasons = []
    
    if fraud_prob >= 0.8:
        reasons.append("ML model shows very high fraud probability")
    elif fraud_prob >= 0.6:
        reasons.append("ML model indicates elevated fraud risk")
    elif fraud_prob >= 0.4:
        reasons.append("ML model shows moderate fraud indicators")
    
    if anomaly_score >= 0.8:
        reasons.append("Transaction is highly anomalous compared to normal patterns")
    elif anomaly_score >= 0.6:
        reasons.append("Transaction shows anomalous characteristics")
    
    return reasons


def get_alert_severity(risk_level: str) -> str:
    """Map risk level to alert severity."""
    severity_map = {
        "CRITICAL": "CRITICAL",
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
    }
    return severity_map.get(risk_level, "LOW")
