"""Demo data generator for testing and demonstration."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict

import numpy as np
import pandas as pd


# Configurable parameters
NUM_TRANSACTIONS = 5000
FRAUD_RATE = 0.05  # 5% fraud

MERCHANTS = [
    "Amazon", "Walmart", "Target", "Best Buy", "Costco",
    "Starbucks", "Uber", "Netflix", "Apple Store", "Home Depot",
    "Shell Gas", "CVS Pharmacy", "McDonald's", "DoorDash", "Airbnb",
    "Western Union", "MoneyGram", "CryptoExchange", "Bet365", "PokerStars",
    "AliExpress", "Offshore Transfer", "Unknown Vendor", "Quick Cash ATM",
]

MERCHANT_CATEGORIES = [
    "retail", "groceries", "food_dining", "entertainment", "transport",
    "utilities", "healthcare", "electronics", "clothing", "travel",
    "crypto", "gambling", "money_transfer", "atm_withdrawal", "online_shopping",
]

LOCATIONS = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "San Francisco", "Miami", "London", "Dubai", "Singapore",
    "Tokyo", "Sydney", "Toronto", "Berlin", "Mumbai",
    "Lagos", "Cayman Islands", "Panama City", "Macau", "Shanghai",
]

COUNTRIES = [
    "US", "UK", "AE", "SG", "JP", "AU", "CA", "DE", "IN", "NG",
    "KY", "PA", "MO", "CN", "BR",
]

DEVICES = [
    "iPhone-15", "iPhone-14", "Samsung-S24", "Samsung-S23", "Pixel-8",
    "Laptop-Chrome", "Laptop-Safari", "Desktop-Win", "Tablet-iPad",
    "Android-Unknown", "Windows-Phone", "Linux-Firefox",
]

PAYMENT_METHODS = [
    "credit_card", "debit_card", "bank_transfer", "digital_wallet",
    "crypto_wallet", "prepaid_card", "wire_transfer",
]

HIGH_RISK_MERCHANTS = {"Western Union", "MoneyGram", "CryptoExchange", "Bet365", "PokerStars",
                        "AliExpress", "Offshore Transfer", "Unknown Vendor", "Quick Cash ATM"}
HIGH_RISK_CATEGORIES = {"crypto", "gambling", "money_transfer", "atm_withdrawal"}


def generate_demo_dataset(
    n_transactions: int = NUM_TRANSACTIONS,
    fraud_rate: float = FRAUD_RATE,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a realistic synthetic fraud detection dataset."""
    np.random.seed(seed)
    random.seed(seed)

    records = []
    base_time = datetime(2024, 1, 1)
    n_fraud = int(n_transactions * fraud_rate)

    # Create users with behavioral profiles
    n_users = n_transactions // 15
    user_profiles = {}
    for i in range(n_users):
        user_profiles[f"USR-{i:05d}"] = {
            "avg_amount": np.random.lognormal(mean=4.5, sigma=1.0),
            "favorite_merchant": random.choice(MERCHANTS[:12]),  # Legitimate merchants
            "favorite_location": random.choice(LOCATIONS[:10]),
            "favorite_device": random.choice(DEVICES[:6]),
            "tx_frequency": np.random.uniform(0.5, 5),  # tx per day
        }

    fraud_indices = set(random.sample(range(n_transactions), n_fraud))

    for i in range(n_transactions):
        is_fraud = i in fraud_indices
        user_id = random.choice(list(user_profiles.keys()))
        profile = user_profiles[user_id]

        # Time
        hours_offset = random.uniform(0, 365 * 24)
        tx_time = base_time + timedelta(hours=hours_offset)
        if is_fraud:
            # Fraud tends to happen at unusual times
            if random.random() < 0.4:
                tx_time = tx_time.replace(hour=random.choice([1, 2, 3, 4, 23]))

        # Amount
        if is_fraud:
            amount = abs(np.random.lognormal(mean=7.0, sigma=1.5))
            amount = min(amount, 500000)
        else:
            amount = abs(np.random.lognormal(mean=4.5, sigma=1.2))
            amount = min(amount, 50000)

        # Merchant
        if is_fraud and random.random() < 0.3:
            merchant = random.choice(list(HIGH_RISK_MERCHANTS))
            category = random.choice(list(HIGH_RISK_CATEGORIES))
        else:
            merchant = random.choice(MERCHANTS[:12])
            category = random.choice(MERCHANT_CATEGORIES[:10])

        # Location
        if is_fraud and random.random() < 0.35:
            location = random.choice(LOCATIONS[10:])  # Exotic locations
            country = random.choice(COUNTRIES[10:])
        else:
            location = profile["favorite_location"]
            country = "US"

        # Device
        if is_fraud and random.random() < 0.3:
            device = random.choice(DEVICES[6:])  # Unknown devices
        else:
            device = profile["favorite_device"]

        # Payment method
        if is_fraud and random.random() < 0.25:
            payment = random.choice(["crypto_wallet", "wire_transfer", "prepaid_card"])
        else:
            payment = random.choice(PAYMENT_METHODS[:5])

        # IP
        ip = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

        records.append({
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "timestamp": tx_time.strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id,
            "amount": round(amount, 2),
            "merchant": merchant,
            "category": category,
            "location": location,
            "country": country,
            "device": device,
            "payment_method": payment,
            "ip_address": ip,
            "fraud": 1 if is_fraud else 0,
        })

    df = pd.DataFrame(records)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    return df


def generate_minimal_dataset(n: int = 200) -> pd.DataFrame:
    """Generate a minimal unlabeled dataset for anomaly detection demo."""
    np.random.seed(42)
    records = []
    base_time = datetime(2024, 6, 1)

    for i in range(n):
        tx_time = base_time + timedelta(hours=random.uniform(0, 30 * 24))
        amount = abs(np.random.lognormal(mean=4.0, sigma=1.5))
        records.append({
            "txn_id": f"TX-{i:06d}",
            "transaction_date": tx_time.strftime("%Y-%m-%d %H:%M:%S"),
            "transaction_amount": round(amount, 2),
            "merchant_name": random.choice(MERCHANTS),
            "category": random.choice(MERCHANT_CATEGORIES),
            "city": random.choice(LOCATIONS),
            "device_type": random.choice(DEVICES),
            "payment_type": random.choice(PAYMENT_METHODS),
        })

    # Inject some anomalies
    for i in range(n // 20):
        idx = random.randint(0, n - 1)
        records[idx]["transaction_amount"] = round(random.uniform(50000, 200000), 2)

    return pd.DataFrame(records)


if __name__ == "__main__":
    # Generate and save demo data
    df = generate_demo_dataset()
    df.to_csv("demo_transactions.csv", index=False)
    print(f"Generated {len(df)} transactions with {df['fraud'].sum()} frauds")
    print(f"Fraud rate: {df['fraud'].mean():.2%}")
