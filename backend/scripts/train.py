"""Standalone training script for fraud detection models."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.demo_data import generate_demo_dataset
from app.ml.schema_detector import detect_schema, detect_target_column
from app.ml.data_profiler import clean_dataset, generate_eda_data
from app.ml.feature_engineering import build_feature_engineering_pipeline
from app.ml.model_trainer import train_models
from app.ml.anomaly_detector import train_anomaly_detector

def main():
    print("=" * 60)
    print("FraudLens - Model Training Pipeline")
    print("=" * 60)

    # Generate demo data
    print("\n[1/6] Generating demo dataset...")
    df = generate_demo_dataset(n_transactions=5000)
    print(f"  Generated {len(df)} transactions, {int(df['fraud'].sum())} frauds ({df['fraud'].mean():.2%})")

    # Detect schema
    print("\n[2/6] Detecting schema...")
    column_map, warnings = detect_schema(df)
    target_col = detect_target_column(df)
    if target_col:
        column_map["fraud_label"] = target_col
    print(f"  Target column: {target_col}")
    for w in warnings:
        print(f"  Warning: {w}")

    # Clean
    print("\n[3/6] Cleaning dataset...")
    df, actions = clean_dataset(df, column_map)
    for a in actions:
        print(f"  {a}")

    # Feature engineering
    print("\n[4/6] Engineering features...")
    df, feature_columns, feature_docs = build_feature_engineering_pipeline(df, column_map)
    print(f"  Generated {len(feature_columns)} features")

    # EDA
    print("\n[5/6] Generating EDA...")
    eda = generate_eda_data(df, column_map)
    if "class_distribution" in eda:
        cd = eda["class_distribution"]
        print(f"  Genuine: {cd['genuine']}, Fraud: {cd['fraud']}, Rate: {cd['fraud_rate']}%")

    # Train models
    print("\n[6/6] Training models...")
    results = train_models(
        df, feature_columns, target_col,
        model_dir="./models_artifacts",
        use_smote=True,
    )

    print(f"\n{'=' * 60}")
    print("Training Complete!")
    print(f"{'=' * 60}")
    print(f"Models: {', '.join(results['models_trained'])}")
    print(f"Best model: {results['best_model']}")
    print(f"Optimal threshold: {results['optimal_threshold']:.2f}")
    print(f"\nModel Comparison:")
    print(f"{'Model':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} {'PR-AUC':>10} {'ROC-AUC':>10}")
    print("-" * 85)
    for name, m in results["metrics"].items():
        print(f"{name:<25} {m['precision']*100:>9.1f}% {m['recall']*100:>9.1f}% {m['f1']*100:>9.1f}% {m['pr_auc']*100:>9.1f}% {m['roc_auc']*100:>9.1f}%")
    print(f"\nArtifacts saved to: {results['model_dir']}")

if __name__ == "__main__":
    main()
