"""Schemas for the Fraud Detection Platform."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ========================================
# Transaction Schemas
# ========================================

class TransactionBase(BaseModel):
    transaction_id: str
    timestamp: Optional[datetime] = None
    amount: Optional[float] = None
    user_id: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    device: Optional[str] = None
    payment_method: Optional[str] = None
    country: Optional[str] = None


class TransactionCreate(TransactionBase):
    """Schema for creating a transaction prediction request."""
    pass


class TransactionResponse(TransactionBase):
    """Schema for a fully processed transaction."""
    id: UUID
    fraud_probability: Optional[float] = None
    anomaly_score: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    prediction: Optional[str] = None
    model_version: Optional[str] = None
    is_simulation: bool = False
    features: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    page: int
    page_size: int


# ========================================
# Alert Schemas
# ========================================

class AlertResponse(BaseModel):
    id: UUID
    alert_id: str
    transaction_id: str
    severity: str
    risk_score: Optional[float] = None
    reasons: Optional[List[str]] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int


# ========================================
# Model Schemas
# ========================================

class ModelInfo(BaseModel):
    model_name: str
    version: str
    model_type: Optional[str] = None
    metrics: Optional[Dict[str, float]] = None
    threshold: Optional[float] = None
    training_date: Optional[datetime] = None
    status: str = "active"
    features_used: Optional[List[str]] = None

    class Config:
        from_attributes = True


class ModelComparison(BaseModel):
    models: List[ModelInfo]


class ThresholdTuningRequest(BaseModel):
    model_name: str = "xgboost"
    thresholds: List[float] = Field(default=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])


class ThresholdResult(BaseModel):
    threshold: float
    precision: float
    recall: float
    f1: float
    flagged_count: int


# ========================================
# Dataset Schemas
# ========================================

class DatasetProfile(BaseModel):
    filename: str
    row_count: int
    column_count: int
    columns: List[Dict[str, Any]]
    missing_values: Dict[str, int]
    duplicate_rows: int
    numerical_columns: List[str]
    categorical_columns: List[str]
    date_columns: List[str]
    possible_target: Optional[str] = None
    has_fraud_label: bool = False
    quality_score: float
    warnings: List[str]


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    profile: DatasetProfile
    message: str


class TrainRequest(BaseModel):
    dataset_id: str
    target_column: Optional[str] = None
    test_size: float = 0.2
    use_smote: bool = True


class TrainResponse(BaseModel):
    models_trained: List[str]
    metrics: Dict[str, Dict[str, float]]
    best_model: str
    dataset_info: Dict[str, Any]


# ========================================
# Dashboard & Analytics Schemas
# ========================================

class DashboardSummary(BaseModel):
    total_transactions: int
    fraud_transactions: int
    fraud_rate: float
    total_fraud_amount: float
    critical_alerts: int
    open_alerts: int
    avg_risk_score: float
    avg_fraud_probability: float
    model_version: Optional[str] = None
    recent_transactions: List[TransactionResponse] = []
    risk_distribution: Dict[str, int] = {}
    recent_alerts: List[AlertResponse] = []


class ExplanationResponse(BaseModel):
    transaction_id: str
    fraud_probability: float
    top_features: List[Dict[str, Any]]
    explanation_text: List[str]


class LiveTransaction(BaseModel):
    """Schema for WebSocket live transaction broadcast."""
    transaction_id: str
    amount: Optional[float] = None
    prediction: Optional[str] = None
    fraud_probability: Optional[float] = None
    anomaly_score: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    merchant: Optional[str] = None
    location: Optional[str] = None
    timestamp: Optional[datetime] = None
    is_alert: bool = False


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    models_loaded: int
    uptime: str
