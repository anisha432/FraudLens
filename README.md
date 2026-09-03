# FraudLens — Real-Time Fraud & Anomaly Detection Intelligence Platform

> A production-quality ML + Data Science flagship project demonstrating the complete fraud detection lifecycle: **Data Science → Machine Learning → Anomaly Detection → Explainable AI → Real-Time Inference → Risk Intelligence → Investigation → Monitoring → Business Intelligence**.

![Architecture](docs/architecture.png)

---

## Problem Statement

Financial fraud costs businesses hundreds of billions of dollars annually. Traditional rule-based systems fail to adapt to evolving fraud patterns. FraudLens demonstrates a modern, ML-driven approach combining supervised classification, unsupervised anomaly detection, explainable AI, and real-time risk intelligence into a cohesive investigation platform.

## Key Capabilities

- **Flexible Dataset Ingestion**: Accepts any CSV/Excel transaction dataset with automatic schema detection
- **Complete ML Pipeline**: Logistic Regression, Random Forest, XGBoost with proper evaluation
- **Anomaly Detection**: Isolation Forest for unlabeled data
- **Explainable AI**: SHAP-based feature importance for model transparency
- **Hybrid Risk Engine**: Combines ML predictions, anomaly scores, and behavioral rules
- **Real-Time Processing**: WebSocket-powered live transaction streaming
- **Investigation Workspace**: Deep-dive analysis with behavioral network visualization
- **Power BI Integration**: Executive-level business intelligence layer

---

## Architecture

```
Transaction Dataset (CSV/Excel)
         ↓
    Data Ingestion + Schema Detection
         ↓
    Validation → Cleaning → EDA
         ↓
    Feature Engineering (30+ features)
         ↓
┌────────────────────────────────────┐
│  Supervised ML                     │
│  • Logistic Regression (Baseline)  │
│  • Random Forest                   │
│  • XGBoost                         │
└────────────────────────────────────┘
         ↓                    ↓
   Fraud Probability    Isolation Forest
         ↓                    ↓
         └──── Hybrid Risk Engine ────┘
                    ↓
              Risk Score (0-100)
                    ↓
              Alert Engine
                    ↓
              PostgreSQL
                    ↓
        ┌───────────┴───────────┐
   FastAPI Backend         Power BI
        ↓
    WebSocket
        ↓
   React Frontend
        ↓
   Fraud Intelligence UI
```

---

## ML Pipeline

### Data Science Workflow

1. **Upload** — CSV or Excel with any column naming convention
2. **Schema Detection** — Automatic identification of transaction ID, amount, timestamp, fraud label, merchant, category, location, device, etc.
3. **Data Quality Profiling** — Missing values, duplicates, type analysis, quality score
4. **Cleaning** — Deduplication, missing value imputation, label mapping
5. **EDA** — Amount distributions, fraud vs genuine comparison, correlation analysis, time patterns
6. **Feature Engineering** — 30+ features including amount, time, behavioral, merchant, location, and device features

### Models

| Model | Type | Strengths |
|-------|------|-----------|
| Logistic Regression | Baseline | Interpretable, fast |
| Random Forest | Ensemble | Robust, handles non-linearity |
| XGBoost | Gradient Boosting | State-of-the-art performance |

### Evaluation Metrics

- **Precision** — Of flagged transactions, how many are truly fraud
- **Recall** — Of actual fraud, how many are caught
- **F1 Score** — Harmonic mean of precision and recall
- **PR-AUC** — Area under Precision-Recall curve (primary metric for imbalanced data)
- **ROC-AUC** — Area under ROC curve

### Class Imbalance Handling

- **SMOTE** — Synthetic Minority Oversampling (training data only)
- **Class Weights** — Automatic balancing in model training
- **Proper Splitting** — SMOTE applied after train/test split to prevent data leakage

### Anomaly Detection

- **Isolation Forest** — Unsupervised detection working independently of fraud labels
- Each transaction receives both a fraud probability (supervised) and anomaly score (unsupervised)

### Threshold Optimization

Multiple thresholds (0.10 to 0.90) evaluated for precision, recall, and F1 to find optimal operating point for fraud detection objectives.

### Explainability

- **Global SHAP** — Feature importance across the dataset
- **Local SHAP** — Why individual transactions were flagged

---

## Real-Time Architecture

```
Transaction Simulator → Feature Processing → ML Models
    ↓                                              ↓
Risk Engine → PostgreSQL → FastAPI → WebSocket → Frontend
    ↓
Alert Engine (CRITICAL/HIGH/MEDIUM/LOW)
```

Features:
- Configurable simulation rate
- WebSocket broadcast for live updates
- Automatic reconnection
- Alert generation for high-risk transactions

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **ML/Data Science** | Python, scikit-learn, XGBoost, SHAP, pandas, NumPy |
| **Backend** | FastAPI, SQLAlchemy, Pydantic |
| **Database** | PostgreSQL |
| **Frontend** | React, TypeScript, Vite |
| **Real-Time** | WebSocket (FastAPI) |
| **BI** | Power BI (via PostgreSQL) |
| **Containerization** | Docker, Docker Compose |

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use Docker)

### Quick Start

```bash
# Clone and enter the project
git clone <repo-url>
cd fraudlens

# Backend
cd backend
pip install -r requirements.txt
python scripts/train.py  # Train on demo data
python run.py             # Start backend on :8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev              # Start frontend on :5173
```

### Docker (Full Stack)

```bash
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/upload/dataset` | Upload CSV/Excel dataset |
| POST | `/api/v1/train` | Train ML models |
| GET | `/api/v1/transactions` | List transactions (paginated) |
| GET | `/api/v1/transactions/{id}` | Get transaction details |
| POST | `/api/v1/transactions/predict` | Predict single transaction |
| GET | `/api/v1/alerts` | List alerts |
| PATCH | `/api/v1/alerts/{id}` | Update alert status |
| GET | `/api/v1/dashboard/summary` | Dashboard summary |
| GET | `/api/v1/models` | Model information |
| GET | `/api/v1/models/compare` | Model comparison |
| POST | `/api/v1/models/threshold` | Threshold analysis |
| GET | `/api/v1/explanations/{tx_id}` | Transaction explanation |
| GET | `/api/v1/eda` | EDA results |
| WS | `/ws/live` | Live transaction stream |
| POST | `/api/v1/simulation/start` | Start simulation |
| POST | `/api/v1/simulation/stop` | Stop simulation |

---

## MLOps Commands

```bash
# Train models on demo data
python scripts/train.py

# Run demo (train + predict + verify)
python scripts/run_demo.py

# Run tests
cd backend && pytest tests/ -v
```

---

## Demo Walkthrough

1. **Upload Dataset** — Drop a CSV/Excel file or use the built-in demo
2. **Schema Detection** — System automatically identifies columns
3. **Data Profiling** — View quality score, missing values, statistics
4. **Train Models** — One-click training of LR, RF, XGBoost
5. **View Comparison** — Model Lab shows all metrics side by side
6. **Start Simulation** — Watch live transactions flow in
7. **Investigate** — Click any suspicious transaction for deep analysis
8. **Explain** — See SHAP-based explanation of why transactions were flagged
9. **Manage Alerts** — Review, resolve, or mark false positives
10. **Analytics** — Explore data patterns and model performance

---

## Power BI Integration

See [docs/powerbi.md](docs/powerbi.md) for complete setup instructions.

Connect Power BI to PostgreSQL for executive-level dashboards including:
- Executive overview with KPIs
- Fraud trends over time
- Risk distribution analysis
- Fraud pattern breakdowns (by category, merchant, location, device)
- Model performance metrics

---

## Testing

```bash
cd backend
pip install pytest
pytest tests/ -v
```

Tests cover:
- Schema detection (flexible column naming)
- Data profiling and cleaning
- Feature engineering
- Model training and evaluation
- Threshold optimization
- Anomaly detection
- Risk engine
- Edge cases

---

## Limitations

- This is a portfolio demonstration project, not a production fraud detection system
- Model performance depends on dataset quality and characteristics
- The real-time simulator generates synthetic data, not real financial transactions
- SHAP explanations require properly trained models
- WebSocket reconnection handles basic disconnections but not all edge cases

## Future Improvements

- Graph Neural Networks for relationship-based fraud detection
- Temporal pattern learning with LSTM/Transformer models
- Feature store for consistent feature computation
- A/B testing framework for model deployment
- Automated model retraining pipeline
- Real-time feature computation with streaming architecture
- User authentication and multi-tenancy
- Audit logging for investigation compliance

---

## License

MIT
