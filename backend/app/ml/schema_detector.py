"""Automatic schema detection for uploaded datasets."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd


# Flexible column name patterns
COLUMN_PATTERNS = {
    "transaction_id": [
        r"transaction.?id", r"txn.?id", r"tx.?id", r"trans.?id",
        r"payment.?id", r"ref.?id", r"reference", r"id$",
    ],
    "user_id": [
        r"user.?id", r"customer.?id", r"account.?id", r"client.?id",
        r"card.?id", r"card.?number", r"acct", r"cid$",
    ],
    "amount": [
        r"amount", r"transaction.?amount", r"txn.?amount", r"value",
        r"price", r"total", r"sum", r"amt",
    ],
    "timestamp": [
        r"timestamp", r"date", r"datetime", r"time", r"created.?at",
        r"trans.?date", r"txn.?date", r"transaction.?date",
        r"transaction.?time", r"trans.?time",
    ],
    "fraud_label": [
        r"fraud", r"is.?fraud", r"fraud.?flag", r"fraud.?label",
        r"class", r"label", r"target", r"anomaly.?label",
        r"is.?anomaly", r"suspicious",
    ],
    "merchant": [
        r"merchant", r"vendor", r"shop", r"store", r"business",
        r"merchant.?name", r"merchant.?id",
    ],
    "category": [
        r"category", r"type", r"trans.?type", r"payment.?type",
        r"txn.?type", r"goods.?type", r"service.?type",
    ],
    "location": [
        r"location", r"city", r"region", r"place", r"address",
        r"merchant.?location", r"trans.?location",
    ],
    "country": [
        r"country", r"nation", r"region.?code", r"country.?code",
    ],
    "device": [
        r"device", r"device.?id", r"device.?type", r"platform",
        r"browser", r"os",
    ],
    "payment_method": [
        r"payment.?method", r"pay.?method", r"payment.?type",
        r"card.?type", r"tender", r"mode.?of.?payment",
    ],
    "ip_address": [
        r"ip.?address", r"ip$", r"ip.?addr", r"remote.?ip",
    ],
    "balance": [
        r"balance", r"remaining.?balance", r"account.?balance",
    ],
    "age": [
        r"age", r"user.?age", r"customer.?age",
    ],
    "gender": [
        r"gender", r"sex", r"user.?gender",
    ],
}


def _normalize(name: str) -> str:
    """Normalize a column name for matching."""
    return re.sub(r"[\s_\-\.]+", "", name.lower().strip())


def _match_column(col_name: str, patterns: List[str]) -> bool:
    """Check if a column name matches any pattern."""
    normalized = _normalize(col_name)
    for pattern in patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            return True
    return False


def detect_schema(df: pd.DataFrame) -> Tuple[Dict[str, Optional[str]], List[str]]:
    """
    Detect possible column roles in a dataframe.
    
    Returns:
        Tuple of (column mapping dict, list of warnings)
    """
    column_map: Dict[str, Optional[str]] = {}
    warnings: List[str] = []
    
    detected_roles: Dict[str, str] = {}  # role -> column_name
    
    for col in df.columns:
        for role, patterns in COLUMN_PATTERNS.items():
            if role in detected_roles:
                continue
            if _match_column(col, patterns):
                # Type validation
                if role == "amount":
                    if pd.api.types.is_numeric_dtype(df[col]):
                        detected_roles[role] = col
                        column_map[role] = col
                elif role == "timestamp":
                    # Accept if it looks like a date
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        detected_roles[role] = col
                        column_map[role] = col
                    elif pd.api.types.is_string_dtype(df[col]):
                        # Try to parse first few non-null values
                        sample = df[col].dropna().head(5)
                        try:
                            pd.to_datetime(sample)
                            detected_roles[role] = col
                            column_map[role] = col
                        except (ValueError, TypeError):
                            pass
                elif role == "fraud_label":
                    if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
                        unique_vals = set(df[col].dropna().unique())
                        if unique_vals.issubset({0, 1, 0.0, 1.0, True, False}):
                            detected_roles[role] = col
                            column_map[role] = col
                    elif pd.api.types.is_string_dtype(df[col]):
                        unique_vals = set(df[col].dropna().str.lower().unique())
                        fraud_words = {"fraud", "true", "yes", "1", "positive", "suspicious", "anomaly"}
                        if unique_vals & fraud_words:
                            detected_roles[role] = col
                            column_map[role] = col
                else:
                    detected_roles[role] = col
                    column_map[role] = col
    
    # Check for missing critical columns
    if "amount" not in column_map:
        # Try to find any numeric column that could be amount
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            # Pick the one with highest average as most likely amount
            best = max(numeric_cols, key=lambda c: abs(df[c].mean()))
            column_map["amount"] = best
            detected_roles["amount"] = best
            warnings.append(f"No explicit amount column detected. Using '{best}' based on numeric analysis.")
        else:
            warnings.append("No amount column detected. ML features may be limited.")
    
    return column_map, warnings


def detect_target_column(df: pd.DataFrame) -> Optional[str]:
    """Specifically detect a fraud/target label column."""
    for col in df.columns:
        if _match_column(col, COLUMN_PATTERNS["fraud_label"]):
            if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
                unique_vals = set(df[col].dropna().unique())
                if unique_vals.issubset({0, 1, 0.0, 1.0, True, False}):
                    return col
            elif pd.api.types.is_string_dtype(df[col]):
                unique_vals = set(df[col].dropna().str.lower().unique())
                fraud_words = {"fraud", "true", "yes", "1", "positive", "suspicious", "anomaly"}
                if unique_vals & fraud_words:
                    return col
    return None


def get_column_types(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Categorize columns by type."""
    result = {
        "numerical": [],
        "categorical": [],
        "date": [],
        "id_like": [],
        "text": [],
    }
    
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            result["date"].append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            nunique = df[col].nunique()
            if nunique <= 20:
                result["categorical"].append(col)
            else:
                result["numerical"].append(col)
        elif pd.api.types.is_string_dtype(df[col]):
            nunique = df[col].nunique()
            if nunique == len(df[col].dropna()):
                result["id_like"].append(col)
            elif nunique <= 50:
                result["categorical"].append(col)
            else:
                result["text"].append(col)
        else:
            result["categorical"].append(col)
    
    return result
