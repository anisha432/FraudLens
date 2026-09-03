"""WebSocket and real-time simulation endpoints — user-scoped."""
from __future__ import annotations

import asyncio
import json
import random
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.auth import get_session
from app.ml.service import ml_service
from app.ml.demo_data import (
    MERCHANTS, LOCATIONS, DEVICES, PAYMENT_METHODS, MERCHANT_CATEGORIES,
)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


class UserConnectionManager:
    """Manages per-user WebSocket connections."""

    def __init__(self):
        self.user_connections: Dict[str, List[WebSocket]] = {}  # user_id -> [websockets]

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def broadcast_to_user(self, user_id: str, data: dict):
        conns = self.user_connections.get(user_id, [])
        message = json.dumps(data, default=str)
        disconnected = []
        for conn in conns:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn, user_id)

    def get_user_connections(self, user_id: str) -> List[WebSocket]:
        return self.user_connections.get(user_id, [])


manager = UserConnectionManager()

# Per-user simulation state: user_id -> {task, running}
_user_simulations: Dict[str, Dict] = {}


def generate_simulated_transaction(tx_num: int) -> dict:
    """Generate a realistic simulated transaction."""
    is_suspicious = random.random() < 0.15
    is_fraud = random.random() < 0.05

    if is_fraud:
        amount = round(random.expovariate(1 / 5000) + 1000, 2)
        merchant = random.choice(MERCHANTS[12:])
        category = random.choice(MERCHANT_CATEGORIES[10:])
        location = random.choice(LOCATIONS[10:])
        device = random.choice(DEVICES[6:])
        payment = random.choice(PAYMENT_METHODS[5:])
        country = random.choice(["KY", "PA", "MO", "NG"])
    elif is_suspicious:
        amount = round(random.expovariate(1 / 2000) + 500, 2)
        merchant = random.choice(MERCHANTS)
        category = random.choice(MERCHANT_CATEGORIES)
        location = random.choice(LOCATIONS)
        device = random.choice(DEVICES)
        payment = random.choice(PAYMENT_METHODS)
        country = random.choice(["US", "UK", "AE"])
    else:
        amount = round(random.expovariate(1 / 200) + 5, 2)
        merchant = random.choice(MERCHANTS[:12])
        category = random.choice(MERCHANT_CATEGORIES[:10])
        location = random.choice(LOCATIONS[:10])
        device = random.choice(DEVICES[:6])
        payment = random.choice(PAYMENT_METHODS[:4])
        country = "US"

    tx_id = f"SIM-{uuid.uuid4().hex[:8].upper()}"

    return {
        "transaction_id": tx_id,
        "timestamp": datetime.utcnow().isoformat(),
        "amount": amount,
        "user_id": f"USR-{random.randint(1000, 9999)}",
        "merchant": merchant,
        "category": category,
        "location": location,
        "country": country,
        "device": device,
        "payment_method": payment,
        "is_simulation": True,
    }


async def _persist_transaction(owner_id: str, payload: dict, alert_payload: dict | None = None):
    """Persist a transaction (and optional alert) to the database, scoped to owner."""
    try:
        from app.db.session import async_session_factory
        if async_session_factory is None:
            return
        async with async_session_factory() as db:
            from app.db.models import Transaction, Alert

            ts = payload.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except Exception:
                    ts = datetime.utcnow()

            features_data = payload.get("features")
            txn = Transaction(
                owner_id=owner_id,
                transaction_id=payload["transaction_id"],
                timestamp=ts,
                amount=payload.get("amount"),
                user_id=payload.get("user_id", ""),
                merchant=payload.get("merchant", ""),
                category=payload.get("category", ""),
                location=payload.get("location", ""),
                device=payload.get("device", ""),
                payment_method=payload.get("payment_method", ""),
                country=payload.get("country", ""),
                fraud_probability=payload.get("fraud_probability"),
                anomaly_score=payload.get("anomaly_score"),
                risk_score=payload.get("risk_score"),
                risk_level=payload.get("risk_level", "LOW"),
                prediction=payload.get("prediction", "GENUINE"),
                model_version=payload.get("model_version", ""),
                is_simulation=True,
                features=features_data if features_data else None,
                created_at=datetime.utcnow(),
            )
            db.add(txn)

            if alert_payload:
                alert = Alert(
                    owner_id=owner_id,
                    alert_id=alert_payload["alert_id"],
                    transaction_id=alert_payload["transaction_id"],
                    severity=alert_payload["severity"],
                    risk_score=alert_payload.get("risk_score"),
                    reasons=alert_payload.get("reasons", []),
                    status="OPEN",
                    created_at=datetime.utcnow(),
                )
                db.add(alert)

            await db.commit()
    except Exception as e:
        logger.error(f"Failed to persist transaction for owner {owner_id}: {e}")


async def simulation_loop(user_id: str, interval: float = None):
    """Run the real-time transaction simulation loop for a specific user."""
    if interval is None:
        interval = settings.SIMULATION_INTERVAL

    _user_simulations[user_id]["running"] = True
    tx_num = 0

    while _user_simulations.get(user_id, {}).get("running", False):
        try:
            tx_num += 1
            transaction = generate_simulated_transaction(tx_num)

            # Get ML prediction for this user's models
            prediction = ml_service.predict_single(user_id, transaction)

            payload = {
                "type": "transaction",
                "transaction_id": prediction["transaction_id"],
                "amount": transaction["amount"],
                "merchant": transaction["merchant"],
                "category": transaction["category"],
                "location": transaction["location"],
                "country": transaction.get("country", ""),
                "device": transaction["device"],
                "payment_method": transaction["payment_method"],
                "user_id": transaction.get("user_id", ""),
                "prediction": prediction["prediction"],
                "fraud_probability": prediction["fraud_probability"],
                "anomaly_score": prediction["anomaly_score"],
                "risk_score": prediction["risk_score"],
                "risk_level": prediction["risk_level"],
                "reasons": prediction["reasons"],
                "model_version": prediction.get("model_version", "sim"),
                "timestamp": prediction["timestamp"],
                "is_simulation": True,
                "features": prediction.get("features", {}),
            }

            # Broadcast ONLY to this user's WebSocket connections
            await manager.broadcast_to_user(user_id, payload)

            # Persist and alert
            alert_payload = None
            if prediction["risk_level"] in ("HIGH", "CRITICAL"):
                alert_payload = {
                    "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "transaction_id": prediction["transaction_id"],
                    "severity": prediction["risk_level"],
                    "risk_score": prediction["risk_score"],
                    "reasons": prediction["reasons"],
                }
                alert_broadcast = {"type": "alert", **alert_payload, "timestamp": prediction["timestamp"]}
                await manager.broadcast_to_user(user_id, alert_broadcast)

            asyncio.create_task(_persist_transaction(user_id, payload, alert_payload))

            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Simulation error for user {user_id}: {e}")
            await asyncio.sleep(1)

    _user_simulations.get(user_id, {})["running"] = False


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket endpoint for live transaction stream — user-scoped."""
    # Authenticate via query param token
    token = websocket.query_params.get("token", "")
    session = get_session(token)
    if not session:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    user_id = session["user_id"]
    await manager.connect(websocket, user_id)

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = json.loads(data)

                if msg.get("action") == "start_simulation":
                    await start_simulation(user_id, msg.get("interval", settings.SIMULATION_INTERVAL))
                elif msg.get("action") == "stop_simulation":
                    stop_simulation(user_id)
                elif msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception:
        manager.disconnect(websocket, user_id)


@router.post("/simulation/start")
async def start_simulation_endpoint(interval: float = 3.0):
    """Start simulation — needs user from token header."""
    # Note: This endpoint is called via REST with auth header
    # The actual user_id must come from the auth dependency
    # For now, simulation is started via WebSocket which has token auth
    return {"status": "use_websocket", "message": "Start simulation via WebSocket connection"}


@router.post("/simulation/stop")
async def stop_simulation_endpoint():
    """Stop simulation — needs user from token header."""
    return {"status": "use_websocket", "message": "Stop simulation via WebSocket connection"}


@router.get("/simulation/status")
async def simulation_status():
    """Get simulation status."""
    # Note: Without auth in this endpoint, we return a generic status
    # The frontend checks simulation status via its own WS connection state
    return {"running": any(s.get("running", False) for s in _user_simulations.values())}


async def start_simulation(user_id: str, interval: float = 3.0):
    """Start the simulation loop for a specific user."""
    if user_id in _user_simulations and _user_simulations[user_id].get("task") and not _user_simulations[user_id]["task"].done():
        return

    _user_simulations[user_id] = {
        "task": asyncio.create_task(simulation_loop(user_id, interval)),
        "running": True,
    }


def stop_simulation(user_id: str):
    """Stop the simulation loop for a specific user."""
    if user_id in _user_simulations:
        _user_simulations[user_id]["running"] = False


def is_simulation_running(user_id: str) -> bool:
    """Check if simulation is running for a specific user."""
    return _user_simulations.get(user_id, {}).get("running", False)
