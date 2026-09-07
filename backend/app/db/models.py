"""Database models for the Fraud Detection Platform — user-scoped."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Text, JSON,
    Index, Boolean, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base model for all database tables."""
    pass


class User(Base):
    """User accounts for authentication."""
    __tablename__ = "users"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(512), nullable=False)
    role = Column(String(50), default="analyst")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


class DatasetInfo(Base):
    """Dataset information — scoped to owner."""
    __tablename__ = "dataset_info"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    schema = Column(JSON, nullable=True)
    quality_score = Column(Float, nullable=True)
    has_fraud_label = Column(Boolean, default=False)
    target_column = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    """Transaction table — scoped to owner."""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    transaction_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=True)

    amount = Column(Float, nullable=True)
    user_id = Column(String(255), nullable=True, index=True)
    merchant = Column(String(500), nullable=True)
    category = Column(String(255), nullable=True)
    location = Column(String(500), nullable=True)
    device = Column(String(500), nullable=True)
    payment_method = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    ip_address = Column(String(255), nullable=True)

    fraud_probability = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_level = Column(String(50), nullable=True)
    prediction = Column(String(50), nullable=True)

    model_version = Column(String(50), nullable=True)
    is_simulation = Column(Boolean, default=False)
    features = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_txn_owner", "owner_id"),
        Index("idx_txn_owner_id", "owner_id", "transaction_id"),
        Index("idx_transaction_risk", "risk_level"),
        Index("idx_transaction_prediction", "prediction"),
        Index("idx_transaction_created", "created_at"),
    )


class Alert(Base):
    """Fraud alert — scoped to owner via transaction."""
    __tablename__ = "alerts"

    # Note: ``transaction_id`` deliberately has NO foreign key to
    # ``transactions.transaction_id``. PostgreSQL (unlike SQLite) requires a
    # foreign-key target to be a primary key or carry a UNIQUE constraint, and
    # ``transaction_id`` is a non-unique business key (user-supplied via
    # /transactions/predict and generated per simulation). Alerts are always
    # inserted in the same commit as their parent transaction (see
    # app/api/v1/ws.py) and all lookups are owner-scoped, so referential
    # integrity is guaranteed by the application flow.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    alert_id = Column(String(255), nullable=False, index=True)
    transaction_id = Column(String(255), nullable=False, index=True)
    severity = Column(String(50), nullable=False)
    risk_score = Column(Float, nullable=True)
    reasons = Column(JSON, nullable=True)
    status = Column(String(50), default="OPEN")
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_alert_owner", "owner_id"),
        Index("idx_alert_status", "status"),
        Index("idx_alert_severity", "severity"),
    )


class ModelRegistry(Base):
    """Model registry — scoped to owner."""
    __tablename__ = "model_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    model_type = Column(String(100), nullable=True)
    metrics = Column(JSON, nullable=True)
    threshold = Column(Float, nullable=True)
    training_date = Column(DateTime, nullable=True)
    dataset_version = Column(String(100), nullable=True)
    status = Column(String(50), default="active")
    features_used = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_model_owner", "owner_id"),
    )


class ActivityLog(Base):
    """User activity audit log."""
    __tablename__ = "activity_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    meta = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
