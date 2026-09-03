"""Data quality profiling and cleaning pipeline - optimized."""
from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd


def profile_dataset(df: pd.DataFrame, column_map: Dict[str, Optional[str]], filename: str = "") -> Dict[str, Any]:
    """
    Generate comprehensive data quality profile for a dataset.
    Optimized: single-pass, conditional calculations.
    """
    rows, cols = df.shape

    # Single pass: compute null counts and unique counts for all columns at once
    null_counts = df.isnull().sum()
    unique_counts = df.nunique()

    # Column info - uses pre-computed values (no repeated scans)
    columns_info = []
    for col in df.columns:
        nc = int(null_counts[col])
        uc = int(unique_counts[col])
        columns_info.append({
            "name": col,
            "dtype": str(df[col].dtype),
            "non_null": rows - nc,
            "null_count": nc,
            "null_pct": round(nc / rows * 100, 2) if rows > 0 else 0,
            "unique_count": uc,
            "sample_values": df[col].dropna().head(3).tolist() if nc < rows else [],
        })

    # Missing values - only non-zero
    missing = {col: int(null_counts[col]) for col in df.columns if null_counts[col] > 0}

    # Duplicate rows - compute once
    duplicate_count = int(df.duplicated().sum())

    # Type categorization
    from app.ml.schema_detector import get_column_types
    col_types = get_column_types(df)

    # Class distribution if target exists
    target_col = column_map.get("fraud_label")
    class_distribution = None
    has_fraud_label = target_col is not None and target_col in df.columns
    if has_fraud_label:
        vc = df[target_col].value_counts()
        class_distribution = {str(k): int(v) for k, v in vc.items()}

    # Quality score - fast conditional calculation
    quality_score = 100.0
    warnings = []

    total_cells = rows * cols
    total_missing = int(null_counts.sum())
    if total_cells > 0:
        missing_pct = total_missing / total_cells * 100
        if missing_pct > 50:
            quality_score -= 30
            warnings.append(f"High missingness: {missing_pct:.1f}% of all cells are empty")
        elif missing_pct > 20:
            quality_score -= 15
            warnings.append(f"Moderate missingness: {missing_pct:.1f}% of cells are empty")
        elif missing_pct > 5:
            quality_score -= 5
            warnings.append(f"Some missing data: {missing_pct:.1f}% of cells are empty")

    if rows > 0:
        dup_pct = duplicate_count / rows * 100
        if dup_pct > 20:
            quality_score -= 20
            warnings.append(f"High duplication: {dup_pct:.1f}% of rows are duplicates")
        elif dup_pct > 5:
            quality_score -= 10
            warnings.append(f"Some duplicate rows: {dup_pct:.1f}% of rows are duplicates")

    # Only check amount/timestamp columns if they exist
    amount_col = column_map.get("amount")
    if amount_col and amount_col in df.columns:
        amt = pd.to_numeric(df[amount_col], errors="coerce")
        non_null_amt = amt.dropna()
        if len(non_null_amt) < len(amt):
            quality_score -= 5
            warnings.append(f"Amount column '{amount_col}' has non-numeric values")
        neg_count = int((non_null_amt < 0).sum()) if len(non_null_amt) > 0 else 0
        if neg_count > 0:
            warnings.append(f"Amount column has {neg_count} negative values")

    ts_col = column_map.get("timestamp")
    if ts_col and ts_col in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df[ts_col]):
            try:
                pd.to_datetime(df[ts_col].dropna().head(5))
            except (ValueError, TypeError):
                quality_score -= 10
                warnings.append(f"Timestamp column '{ts_col}' has parsing issues")

    if rows < 100:
        quality_score -= 10
        warnings.append(f"Small dataset: only {rows} rows. ML results may be unreliable.")
    if rows < 30:
        quality_score -= 15
        warnings.append(f"Very small dataset ({rows} rows). Model training may not be meaningful.")

    if not has_fraud_label:
        quality_score -= 5
        warnings.append("No fraud label detected. System will operate in anomaly-detection mode.")

    quality_score = max(0, min(100, quality_score))

    return {
        "filename": filename,
        "row_count": rows,
        "column_count": cols,
        "columns": columns_info,
        "missing_values": missing,
        "duplicate_rows": duplicate_count,
        "numerical_columns": col_types["numerical"],
        "categorical_columns": col_types["categorical"],
        "date_columns": col_types["date"],
        "possible_target": target_col,
        "has_fraud_label": has_fraud_label,
        "class_distribution": class_distribution,
        "quality_score": round(quality_score, 1),
        "warnings": warnings,
    }


def clean_dataset(df: pd.DataFrame, column_map: Dict[str, Optional[str]]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Clean a dataset based on detected schema.
    OPTIMIZED: Only performs cleaning actions that are actually needed.
    """
    actions = []
    df = df.copy()

    # Drop completely empty columns
    empty_cols = [col for col in df.columns if null_pct_all(df[col])]
    if empty_cols:
        df = df.drop(columns=empty_cols)
        actions.append(f"Dropped {len(empty_cols)} empty columns")

    # Remove duplicate rows - skip if no duplicates
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        df = df.drop_duplicates()
        actions.append(f"Removed {dup_count} duplicate rows")

    # Clean amount column - skip if already numeric and no nulls
    amount_col = column_map.get("amount")
    if amount_col and amount_col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[amount_col]):
            df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")
        null_amt = df[amount_col].isnull().sum()
        if null_amt > 0:
            median_val = df[amount_col].median()
            df[amount_col] = df[amount_col].fillna(median_val)
            actions.append(f"Filled {amount_col} missing values with median ({median_val:.2f})")

    # Clean timestamp - skip if already datetime
    ts_col = column_map.get("timestamp")
    if ts_col and ts_col in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df[ts_col]):
            df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
            unparseable = int(df[ts_col].isnull().sum())
            if unparseable > 0:
                actions.append(f"Note: {unparseable} unparseable timestamps converted to NaT")

    # Clean fraud label - skip if already integer 0/1
    target_col = column_map.get("fraud_label")
    if target_col and target_col in df.columns:
        if pd.api.types.is_string_dtype(df[target_col]):
            label_map = {
                "fraud": 1, "true": 1, "yes": 1, "positive": 1, "suspicious": 1, "anomaly": 1,
                "legitimate": 0, "false": 0, "no": 0, "negative": 0, "normal": 0, "genuine": 0,
            }
            df[target_col] = df[target_col].str.lower().map(label_map)
            df[target_col] = df[target_col].fillna(0).astype(int)
            actions.append("Mapped string fraud labels to numeric")
        elif not pd.api.types.is_integer_dtype(df[target_col]):
            df[target_col] = df[target_col].astype(int)

    # Fill missing categoricals - only where needed
    for col in df.select_dtypes(include=["object"]).columns:
        nc = df[col].isnull().sum()
        if nc > 0:
            df[col] = df[col].fillna("unknown")

    df = df.reset_index(drop=True)

    if not actions:
        actions.append("Dataset already clean — no cleaning actions needed")

    return df, actions


def null_pct_all(series: pd.Series) -> bool:
    """Check if all values are null."""
    return series.isnull().all()


def generate_eda_data(df: pd.DataFrame, column_map: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """Generate EDA summary data from cleaned dataset."""
    eda: Dict[str, Any] = {}

    amount_col = column_map.get("amount")
    target_col = column_map.get("fraud_label")
    ts_col = column_map.get("timestamp")

    eda["summary"] = {
        "total_transactions": len(df),
        "total_columns": len(df.columns),
    }

    if amount_col and amount_col in df.columns:
        amt = pd.to_numeric(df[amount_col], errors="coerce")
        eda["amount_stats"] = {
            "mean": float(amt.mean()),
            "median": float(amt.median()),
            "std": float(amt.std()) if len(amt) > 1 else 0,
            "min": float(amt.min()),
            "max": float(amt.max()),
            "q25": float(amt.quantile(0.25)),
            "q75": float(amt.quantile(0.75)),
        }
        hist_values, hist_edges = np.histogram(amt.dropna(), bins=30)
        eda["amount_distribution"] = {
            "counts": hist_values.tolist(),
            "bins": hist_edges.tolist(),
        }

    if target_col and target_col in df.columns:
        fraud_count = int(df[target_col].sum())
        genuine_count = len(df) - fraud_count
        eda["class_distribution"] = {
            "genuine": genuine_count,
            "fraud": fraud_count,
            "fraud_rate": round(fraud_count / len(df) * 100, 2) if len(df) > 0 else 0,
        }
        if amount_col and amount_col in df.columns:
            fraud_amounts = df[df[target_col] == 1][amount_col]
            genuine_amounts = df[df[target_col] == 0][amount_col]
            eda["fraud_amount_stats"] = {
                "fraud_mean": float(fraud_amounts.mean()) if len(fraud_amounts) > 0 else 0,
                "fraud_median": float(fraud_amounts.median()) if len(fraud_amounts) > 0 else 0,
                "genuine_mean": float(genuine_amounts.mean()) if len(genuine_amounts) > 0 else 0,
                "genuine_median": float(genuine_amounts.median()) if len(genuine_amounts) > 0 else 0,
            }

    if ts_col and ts_col in df.columns:
        ts_data = pd.to_datetime(df[ts_col], errors="coerce").dropna()
        if len(ts_data) > 0:
            eda["time_analysis"] = {
                "date_range_start": str(ts_data.min()),
                "date_range_end": str(ts_data.max()),
                "hour_distribution": ts_data.dt.hour.value_counts().sort_index().to_dict(),
                "day_distribution": ts_data.dt.dayofweek.value_counts().sort_index().to_dict(),
            }

    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) > 1:
        corr = numeric_df.corr()
        eda["correlation_matrix"] = {
            "columns": corr.columns.tolist(),
            "values": corr.values.tolist(),
        }

    eda["categorical_distributions"] = {}
    for col in df.select_dtypes(include=["object", "category"]).columns:
        if df[col].nunique() <= 30:
            eda["categorical_distributions"][col] = df[col].value_counts().head(15).to_dict()

    return eda
