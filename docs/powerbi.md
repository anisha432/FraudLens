# Power BI Business Intelligence Layer

## Architecture

```
ML System (FastAPI) → PostgreSQL → Power BI
```

Power BI connects directly to PostgreSQL to create executive-level fraud analytics dashboards.

## Database Connection

### Connection Settings
- **Server**: `localhost:5432` (or Docker service name: `postgres`)
- **Database**: `fraud_detection`
- **Username**: `fraud_user`
- **Password**: `fraud_pass`
- **Driver**: PostgreSQL ANSI

### Connection String (for Power BI)
```
PostgreSQL;Server=localhost;Port=5432;Database=fraud_detection;Uid=fraud_user;Pwd=fraud_pass;
```

## Data Model

### Tables

#### `transactions`
| Column | Type | Description |
|--------|------|-------------|
| transaction_id | VARCHAR | Unique transaction identifier |
| timestamp | TIMESTAMP | Transaction datetime |
| amount | FLOAT | Transaction amount |
| user_id | VARCHAR | Customer identifier |
| merchant | VARCHAR | Merchant name |
| category | VARCHAR | Transaction category |
| location | VARCHAR | Transaction location |
| country | VARCHAR | Country code |
| device | VARCHAR | Device used |
| payment_method | VARCHAR | Payment method |
| fraud_probability | FLOAT | ML fraud probability (0-1) |
| anomaly_score | FLOAT | Anomaly detection score (0-1) |
| risk_score | FLOAT | Hybrid risk score (0-100) |
| risk_level | VARCHAR | LOW/MEDIUM/HIGH/CRITICAL |
| prediction | VARCHAR | FRAUD/GENUINE |
| model_version | VARCHAR | ML model version |
| is_simulation | BOOLEAN | Whether this is simulated data |
| created_at | TIMESTAMP | Record creation time |

#### `alerts`
| Column | Type | Description |
|--------|------|-------------|
| alert_id | VARCHAR | Unique alert identifier |
| transaction_id | VARCHAR | Related transaction |
| severity | VARCHAR | LOW/MEDIUM/HIGH/CRITICAL |
| risk_score | FLOAT | Risk score at time of alert |
| reasons | JSON | Why the alert was generated |
| status | VARCHAR | OPEN/REVIEWING/RESOLVED/FALSE_POSITIVE |
| created_at | TIMESTAMP | Alert creation time |
| resolved_at | TIMESTAMP | Resolution time |

#### `model_registry`
| Column | Type | Description |
|--------|------|-------------|
| model_name | VARCHAR | Model identifier |
| version | VARCHAR | Version string |
| metrics | JSON | Model performance metrics |
| threshold | FLOAT | Classification threshold |
| training_date | TIMESTAMP | When the model was trained |
| status | VARCHAR | Model status |

## Recommended Power BI Dashboard Pages

### 1. Executive Overview
- **KPI Cards**: Total Transactions, Fraud Rate, Total Fraud Amount, Critical Alerts, Avg Risk Score
- **Fraud Rate Gauge**: Dial chart showing fraud percentage
- **Risk Distribution**: Donut chart by risk level
- **Trend Line**: Fraud rate over time

### 2. Fraud Trends
- **Time Series**: Transaction volume and fraud count over time
- **Fraud Rate Trend**: Line chart showing fraud rate percentage
- **Peak Hours**: Heatmap of fraud by hour and day of week
- **Monthly Comparison**: Bar chart comparing fraud across months

### 3. Risk Analysis
- **Risk Score Distribution**: Histogram of risk scores
- **High-Risk Transactions**: Table of transactions with risk_score > 60
- **Anomaly vs Fraud**: Scatter plot comparing anomaly scores and fraud probability
- **Risk Level Trend**: Stacked area chart of risk levels over time

### 4. Fraud Patterns
- **Fraud by Category**: Bar chart of fraud count by transaction category
- **Fraud by Merchant**: Top merchants by fraud volume
- **Fraud by Location**: Map or bar chart of fraud by location
- **Fraud by Payment Method**: Donut chart showing fraud distribution across payment methods
- **Amount Analysis**: Box plot comparing amounts for fraud vs genuine

### 5. Model Performance
- **Model Comparison**: Table comparing precision, recall, F1, PR-AUC, ROC-AUC
- **Threshold Impact**: Line chart showing precision/recall at different thresholds
- **Confusion Matrix**: Matrix visualization

### 6. Alert Management
- **Alert Summary**: Cards for Open, Reviewing, Resolved alerts
- **Alert Age**: How long alerts have been open
- **Alert Trend**: New alerts over time

## DAX Measures (Examples)

```dax
Fraud Rate = 
DIVIDE(
    COUNTROWS(FILTER(transactions, transactions[prediction] = "FRAUD")),
    COUNTROWS(transactions),
    0
) * 100

Total Fraud Amount = 
CALCULATE(
    SUM(transactions[amount]),
    transactions[prediction] = "FRAUD"
)

Avg Risk Score = AVERAGE(transactions[risk_score])

Open Alerts = 
CALCULATE(
    COUNTROWS(alerts),
    alerts[status] = "OPEN"
)

Critical Rate = 
DIVIDE(
    COUNTROWS(FILTER(transactions, transactions[risk_level] = "CRITICAL")),
    COUNTROWS(transactions),
    0
) * 100
```

## Step-by-Step Setup

1. **Start the application** (backend + PostgreSQL)
2. **Open Power BI Desktop**
3. **Get Data → PostgreSQL**
4. **Enter connection details** (see above)
5. **Select tables**: `transactions`, `alerts`, `model_registry`
6. **Load data** and create relationships
7. **Build visualizations** per the recommended dashboard pages
8. **Publish** to Power BI Service for sharing
