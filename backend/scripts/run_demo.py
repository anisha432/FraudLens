"""Demo runner - generates data, trains models, and runs simulation."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.demo_data import generate_demo_dataset
from app.ml.schema_detector import detect_schema, detect_target_column
from app.ml.data_profiler import clean_dataset
from app.ml.feature_engineering import build_feature_engineering_pipeline
from app.ml.model_trainer import train_models
from app.ml.service import ml_service

def main():
    print("FraudLens Demo Mode")
    print("=" * 40)

    # Generate and upload data
    df = generate_demo_dataset(5000)
    result = ml_service.upload_dataset(df, "demo_transactions.csv")
    print(f"Uploaded: {result['dataset_id']}")

    # Train
    print("Training models...")
    train_result = ml_service.train(result["dataset_id"])
    print(f"Best model: {train_result['best_model']}")
    print(f"Threshold: {train_result['optimal_threshold']}")

    # Test predictions
    print("\nTesting predictions...")
    test_tx = {
        "transaction_id": "TEST-001",
        "amount": 85000,
        "merchant": "Unknown Vendor",
        "category": "crypto",
        "location": "Cayman Islands",
        "device": "Android-Unknown",
        "payment_method": "crypto_wallet",
    }
    pred = ml_service.predict_single(test_tx)
    print(f"  Transaction: ${test_tx['amount']:,}")
    print(f"  Prediction: {pred['prediction']}")
    print(f"  Fraud Probability: {pred['fraud_probability']:.1%}")
    print(f"  Anomaly Score: {pred['anomaly_score']:.2f}")
    print(f"  Risk Score: {pred['risk_score']:.0f}")
    print(f"  Risk Level: {pred['risk_level']}")
    print(f"  Reasons:")
    for r in pred['reasons']:
        print(f"    • {r}")

    print("\nDemo complete! Start the backend to use the web interface.")
    print("  cd backend && python run.py")

if __name__ == "__main__":
    main()
