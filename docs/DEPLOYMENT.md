# FraudLens — Production Deployment Guide

## Overview

FraudLens is a Real-Time Fraud & Anomaly Detection Intelligence Platform with:
- **Backend**: FastAPI + SQLAlchemy + ML pipeline
- **Frontend**: React + TypeScript + Vite
- **Database**: PostgreSQL (production) / SQLite (local dev fallback)
- **ML**: scikit-learn, XGBoost, SHAP explainability
- **Real-time**: WebSocket-based live transaction simulation

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL (optional — SQLite fallback works without it)

### 1. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your settings
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### 3. Access
- Open http://localhost:5173
- Login with demo credentials: `admin@fraudlens.io` / `fraudlens`
- Or create a new account

---

## Environment Variables

### Backend (.env)
```env
# Database
DATABASE_URL=postgresql+asyncpg://fraud_user:password@localhost:5432/fraud_detection
DATABASE_URL_SYNC=postgresql://fraud_user:password@localhost:5432/fraud_detection

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# CORS (production: your frontend domain)
CORS_ORIGINS=["https://your-app.onrender.com"]

# ML
MODELS_DIR=./models_artifacts
DEFAULT_THRESHOLD=0.5

# Simulation
SIMULATION_INTERVAL=3.0
SIMULATION_ENABLED=true

# Logging
LOG_LEVEL=INFO
```

### Frontend (Build-time env vars)
```env
# Production: set your backend URL
VITE_API_URL=https://your-backend.onrender.com/api/v1
VITE_WS_URL=wss://your-backend.onrender.com

# Local dev: leave unset (Vite proxy handles /api and /ws)
```

---

## Deploy to Render (Recommended)

### Backend Service
1. **Create a new Web Service** on Render
2. **Source**: Connect your GitHub repo
3. **Settings**:
   - **Root Directory**: `backend`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**:
   - `DATABASE_URL`: PostgreSQL connection string (use Render's managed PostgreSQL)
   - `DATABASE_URL_SYNC`: Same but without `+asyncpg`
   - `DEBUG`: `false`
   - `CORS_ORIGINS`: `["https://your-frontend.onrender.com"]`
   - `LOG_LEVEL`: `INFO`
   - `MODELS_DIR`: `./models_artifacts`
5. **Add a PostgreSQL database** from Render dashboard

### Frontend Service
1. **Create a new Static Site** on Render
2. **Source**: Connect your GitHub repo
3. **Settings**:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`
4. **Environment Variables**:
   - `VITE_API_URL`: `https://your-backend.onrender.com/api/v1`
   - `VITE_WS_URL`: `wss://your-backend.onrender.com`

---

## Deploy with Docker

### Docker Compose (all-in-one)
```bash
# Set your PostgreSQL password
export POSTGRES_PASSWORD=your_secure_password

docker-compose up -d --build
```

This starts:
- PostgreSQL on port 5432
- Backend on port 8000
- Frontend (nginx) on port 3000

### Individual Docker Builds
```bash
# Backend
docker build -f Dockerfile.backend -t fraudlens-backend .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://... \
  fraudlens-backend

# Frontend
docker build -f Dockerfile.frontend -t fraudlens-frontend .
docker run -p 3000:3000 fraudlens-frontend
```

---

## Architecture

### User Data Isolation
Every user has their own isolated workspace:
- **Datasets** — scoped to `owner_id`
- **Transactions** — scoped to `owner_id`
- **Alerts** — scoped to `owner_id`
- **Models** — scoped to `owner_id`
- **Activity logs** — scoped to `owner_id`

A new user starts with a completely clean workspace.

### ML Pipeline
1. **Upload** → CSV/XLSX ingestion
2. **Schema Detection** → column types, target detection
3. **Data Profiling** → missing values, duplicates, quality score
4. **Feature Engineering** → dynamic based on dataset schema
5. **Model Training** → Logistic Regression, Random Forest, XGBoost, Isolation Forest
6. **Risk Scoring** → hybrid fraud probability + anomaly detection

### Real-time Simulation
- WebSocket-based live transaction generation
- Per-user simulation (no cross-user interference)
- Automatic alert generation for HIGH/CRITICAL risk
- All transactions persisted to database

### Authentication
- Bearer token authentication
- bcrypt password hashing (12 rounds)
- Per-user session management
- Protected API routes via `get_current_user` dependency

---

## Important Notes

### ML Model Artifacts
- Models are trained per-user and stored in `models_artifacts/`
- This directory is gitignored (generated data)
- After deployment, models are trained from scratch when users upload datasets
- Global model fallback loads from disk if available

### SQLite vs PostgreSQL
- **SQLite** is the local development fallback (no setup required)
- **PostgreSQL** is recommended for production
- The app auto-detects and falls back gracefully

### Session Storage
- Sessions are in-memory (fast, simple)
- For production at scale, consider Redis or database sessions
- Sessions do not survive backend restarts (users re-login)

### CORS
- **DEBUG=true**: Allows all origins (development convenience)
- **DEBUG=false**: Uses only configured `CORS_ORIGINS` list

### WebSocket
- Authentication via query parameter token
- Per-user connection management
- Automatic reconnection in frontend
- Heartbeat/ping-pong keepalive

---

## Testing Checklist

After deployment, verify:
- [ ] Health endpoint returns 200 without auth
- [ ] Registration creates new account
- [ ] Login returns valid token
- [ ] Protected endpoints require auth
- [ ] New user sees clean workspace
- [ ] Demo dataset loads and trains
- [ ] CSV upload works
- [ ] Simulation generates transactions
- [ ] WebSocket connects and streams
- [ ] Transactions page shows persisted data
- [ ] Alerts generated for high-risk transactions
- [ ] Investigation page loads transaction details
- [ ] SHAP explanations work (individual + global)
- [ ] Analytics/Power BI dashboard shows real data
- [ ] User isolation: User B cannot see User A's data
- [ ] Logout clears session
- [ ] No console errors in browser

---

## Files Changed for Production Readiness

| File | Change |
|------|--------|
| `frontend/src/api.ts` | API_BASE/WS_BASE use VITE_API_URL/VITE_WS_URL env vars with localhost fallback |
| `frontend/vite.config.ts` | Added dev proxy for /api and /ws, production build config |
| `backend/app/main.py` | CORS uses config settings in production (DEBUG=false), allows all in dev |
| `.env.example` | Production-ready with documentation for all env vars |
| `Dockerfile.backend` | Production start command reads $PORT, supports $WORKERS |
| `docker-compose.yml` | Environment variables with secure defaults |
| `nginx.conf` | WebSocket proxy with extended timeouts, health endpoint |
| `docs/DEPLOYMENT.md` | This file |

---

## Render Deployment Settings (Quick Reference)

**Backend Web Service:**
```
Root Directory:    backend
Build Command:     pip install -r requirements.txt
Start Command:     uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Frontend Static Site:**
```
Root Directory:    frontend
Build Command:     npm install && npm run build
Publish Directory: dist
```

**Environment Variables:**
```
VITE_API_URL=https://your-backend.onrender.com/api/v1
VITE_WS_URL=wss://your-backend.onrender.com
DATABASE_URL=postgresql+asyncpg://user:pass@your-render-db:5432/fraud_detection
DATABASE_URL_SYNC=postgresql://user:pass@your-render-db:5432/fraud_detection
DEBUG=false
CORS_ORIGINS=["https://your-frontend.onrender.com"]
```
