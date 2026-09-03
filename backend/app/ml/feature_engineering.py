"""Feature engineering pipeline - optimized, schema-aware."""
from __future__ import annotations

import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)


FEATURE_DOCS: Dict[str, str] = {
    "amount": "Raw transaction amount",
    "log_amount": "Log-transformed amount to reduce skewness",
    "amount_deviation": "How much this amount deviates from user's average",
    "amount_percentile": "Percentile rank of amount in overall distribution",
    "amount_vs_avg": "Ratio of amount to overall average",
    "hour": "Hour of transaction (0-23)",
    "day_of_week": "Day of week (0=Monday, 6=Sunday)",
    "is_weekend": "Whether transaction occurred on a weekend",
    "is_unusual_hour": "Whether transaction is between 11pm-5am (unusual hours)",
    "is_month_end": "Whether transaction is near month end (25th-31st)",
    "user_tx_count": "Number of transactions by this user",
    "user_avg_amount": "Average transaction amount for this user",
    "user_std_amount": "Standard deviation of user's transaction amounts",
    "user_spending_deviation": "How much this amount deviates from user's average (z-score)",
    "user_tx_frequency": "Average daily transaction frequency for this user",
    "merchant_frequency": "How common this merchant is in the dataset",
    "merchant_avg_amount": "Average transaction amount at this merchant",
    "category_frequency": "How common this category is in the dataset",
    "category_avg_amount": "Average transaction amount in this category",
    "location_frequency": "How common this location is in the dataset",
    "device_frequency": "How common this device is in the dataset",
    "is_new_device": "Whether this device has been seen less than 3 times",
    "location_change": "Whether the location changed from the previous transaction",
    "amount_binned": "Amount bucketed into quantiles",
    "rolling_mean_5": "Rolling mean amount over last 5 transactions (by user)",
    "rolling_std_5": "Rolling std of amount over last 5 transactions (by user)",
    "time_since_last_tx": "Seconds since the user's last transaction",
}


def _has_column(column_map: Dict, role: str) -> bool:
    """Check if a required column exists in the schema."""
    col = column_map.get(role)
    return col is not None and col != ""


def build_feature_engineering_pipeline(
    df: pd.DataFrame,
    column_map: Dict[str, Optional[str]],
) -> Tuple[pd.DataFrame, List[str], Dict[str, str]]:
    """
    Build feature engineering pipeline — schema-aware.
    Only creates features when the required source columns exist.
    """
    df = df.copy()

    # Track which feature groups we actually create
    created_features: List[str] = []
    has_amount = _has_column(column_map, "amount") and column_map["amount"] in df.columns
    has_timestamp = _has_column(column_map, "timestamp") and column_map["timestamp"] in df.columns
    has_user = _has_column(column_map, "user_id") and column_map["user_id"] in df.columns
    has_merchant = _has_column(column_map, "merchant") and column_map["merchant"] in df.columns
    has_category = _has_column(column_map, "category") and column_map["category"] in df.columns
    has_location = _has_column(column_map, "location") and column_map["location"] in df.columns
    has_device = _has_column(column_map, "device") and column_map["device"] in df.columns

    # ========== AMOUNT FEATURES ==========
    if has_amount:
        amt_col = column_map["amount"]
        amt = pd.to_numeric(df[amt_col], errors="coerce").fillna(0)
        df["amount"] = amt
        df["log_amount"] = np.log1p(amt.clip(lower=0))

        global_mean = amt.mean()
        global_std = amt.std() if amt.std() > 0 else 1
        df["amount_deviation"] = (amt - global_mean) / global_std
        df["amount_percentile"] = amt.rank(pct=True)
        df["amount_vs_avg"] = amt / (global_mean if global_mean > 0 else 1)

        try:
            df["amount_binned"] = pd.qcut(amt.rank(method="first"), q=10, labels=False, duplicates="drop")
        except ValueError:
            df["amount_binned"] = 0

        created_features.extend(["amount", "log_amount", "amount_deviation", "amount_percentile", "amount_vs_avg", "amount_binned"])
    else:
        # Fallback: use first numeric column
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            col = numeric_cols[0]
            df["amount"] = df[col]
            df["log_amount"] = np.log1p(df[col].clip(lower=0))
            gmean = df[col].mean()
            gstd = df[col].std() if df[col].std() > 0 else 1
            df["amount_deviation"] = (df[col] - gmean) / gstd
            df["amount_percentile"] = df[col].rank(pct=True)
            df["amount_vs_avg"] = df[col] / (gmean if gmean > 0 else 1)
            created_features.extend(["amount", "log_amount", "amount_deviation", "amount_percentile", "amount_vs_avg"])

    # ========== TIME FEATURES ==========
    if has_timestamp:
        ts_col = column_map["timestamp"]
        ts = pd.to_datetime(df[ts_col], errors="coerce")
        df["hour"] = ts.dt.hour.fillna(12).astype(int)
        df["day_of_week"] = ts.dt.dayofweek.fillna(0).astype(int)
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
        df["is_unusual_hour"] = ((df["hour"] >= 23) | (df["hour"] <= 5)).astype(int)
        df["is_month_end"] = (ts.dt.day >= 25).astype(int)
        df["day_of_month"] = ts.dt.day.fillna(15).astype(int)
        df["month"] = ts.dt.month.fillna(6).astype(int)
        created_features.extend(["hour", "day_of_week", "is_weekend", "is_unusual_hour", "is_month_end", "day_of_month", "month"])
    else:
        # Constants when no timestamp — minimal features
        df["hour"] = 12
        df["day_of_week"] = 0
        df["is_weekend"] = 0
        df["is_unusual_hour"] = 0
        df["is_month_end"] = 0
        df["day_of_month"] = 15
        df["month"] = 6

    # ========== USER BEHAVIOR FEATURES ==========
    if has_user and has_amount:
        user_col = column_map["user_id"]
        user_groups = df.groupby(user_col)
        df["user_tx_count"] = user_groups["amount"].transform("count")
        df["user_avg_amount"] = user_groups["amount"].transform("mean")
        df["user_std_amount"] = user_groups["amount"].transform("std").fillna(0)
        user_std = df["user_std_amount"].replace(0, 1)
        df["user_spending_deviation"] = (df["amount"] - df["user_avg_amount"]) / user_std

        if has_timestamp:
            ts = pd.to_datetime(df[column_map["timestamp"]], errors="coerce")
            date_range = ts.groupby(df[user_col]).transform(lambda x: (x.max() - x.min()).days)
            date_range = date_range.fillna(1).replace(0, 1)
            df["user_tx_frequency"] = df["user_tx_count"] / date_range
        else:
            df["user_tx_frequency"] = df["user_tx_count"]

        created_features.extend(["user_tx_count", "user_avg_amount", "user_std_amount", "user_spending_deviation", "user_tx_frequency"])
    else:
        df["user_tx_count"] = 1
        df["user_avg_amount"] = df.get("amount", pd.Series([0]))
        df["user_std_amount"] = 0
        df["user_spending_deviation"] = 0
        df["user_tx_frequency"] = 1

    # ========== MERCHANT / CATEGORY FEATURES ==========
    if has_merchant and has_amount:
        mcol = column_map["merchant"]
        mgrp = df.groupby(mcol)
        df["merchant_frequency"] = mgrp["amount"].transform("count")
        df["merchant_avg_amount"] = mgrp["amount"].transform("mean")
        created_features.extend(["merchant_frequency", "merchant_avg_amount"])
    else:
        df["merchant_frequency"] = 1
        df["merchant_avg_amount"] = df.get("amount", pd.Series([0]))

    if has_category and has_amount:
        ccol = column_map["category"]
        cgrp = df.groupby(ccol)
        df["category_frequency"] = cgrp["amount"].transform("count")
        df["category_avg_amount"] = cgrp["amount"].transform("mean")
        created_features.extend(["category_frequency", "category_avg_amount"])
    else:
        df["category_frequency"] = 1
        df["category_avg_amount"] = df.get("amount", pd.Series([0]))

    # ========== LOCATION / DEVICE FEATURES ==========
    if has_location:
        lcol = column_map["location"]
        df["location_frequency"] = df.groupby(lcol)[lcol].transform("count")
        created_features.append("location_frequency")
    else:
        df["location_frequency"] = 1

    if has_device:
        dcol = column_map["device"]
        device_counts = df[dcol].value_counts()
        df["device_frequency"] = df[dcol].map(device_counts).fillna(1).astype(int)
        df["is_new_device"] = (df["device_frequency"] <= 3).astype(int)
        created_features.extend(["device_frequency", "is_new_device"])
    else:
        df["device_frequency"] = 1
        df["is_new_device"] = 0

    # ========== ROLLING / VELOCITY FEATURES ==========
    if has_user and has_amount:
        user_col = column_map["user_id"]
        if has_timestamp:
            df = df.sort_values([user_col, column_map["timestamp"]])

        df["rolling_mean_5"] = df.groupby(user_col)["amount"].transform(
            lambda x: x.rolling(window=5, min_periods=1).mean()
        )
        df["rolling_std_5"] = df.groupby(user_col)["amount"].transform(
            lambda x: x.rolling(window=5, min_periods=1).std().fillna(0)
        )

        if has_timestamp:
            ts = pd.to_datetime(df[column_map["timestamp"]], errors="coerce")
            df["_ts_num"] = ts.astype(np.int64) / 1e9
            df["time_since_last_tx"] = df.groupby(user_col)["_ts_num"].diff().fillna(86400).clip(lower=0)
            df = df.drop(columns=["_ts_num"], errors="ignore")
        else:
            df["time_since_last_tx"] = 0

        created_features.extend(["rolling_mean_5", "rolling_std_5", "time_since_last_tx"])
    else:
        df["rolling_mean_5"] = df.get("amount", 0)
        df["rolling_std_5"] = 0
        df["time_since_last_tx"] = 0

    # ========== ENCODE CATEGORICALS ==========
    cat_cols = []
    for role in ["category", "payment_method", "country", "gender"]:
        col = column_map.get(role)
        if col and col in df.columns and df[col].dtype == object and df[col].nunique() <= 20:
            cat_cols.append(col)

    for col in cat_cols:
        dummies = pd.get_dummies(df[col], prefix=col, drop_first=True, dtype=int)
        df = pd.concat([df, dummies], axis=1)

    # ========== FINAL FEATURE COLUMNS ==========
    drop_cols = []
    target_col = column_map.get("fraud_label")
    for col in df.columns:
        if df[col].dtype == object:
            if col == target_col:
                continue
            drop_cols.append(col)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            drop_cols.append(col)

    feature_columns = [c for c in df.columns if c not in drop_cols and c != target_col]

    feature_docs = {}
    for feat in feature_columns:
        feature_docs[feat] = FEATURE_DOCS.get(feat, f"Engineered feature: {feat}")

    return df, feature_columns, feature_docs
