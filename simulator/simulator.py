import requests
import time
import random
import uuid
from datetime import datetime, timedelta, timezone
from faker import Faker

fake = Faker()

BACKEND_URL = "http://localhost:8000/audit_transaction"

CITY_COORDS = {
    "Mumbai, IN":       {"lat": 19.0760, "lon": 72.8777},
    "London, UK":       {"lat": 51.5074, "lon": -0.1278},
    "New York, US":     {"lat": 40.7128, "lon": -74.0060},
    "Tokyo, JP":        {"lat": 35.6762, "lon": 139.6503},
    "Dubai, AE":        {"lat": 25.2048, "lon": 55.2708},
    "Sydney, AU":       {"lat": -33.8688, "lon": 151.2093},
    "Frankfurt, DE":    {"lat": 50.1109, "lon": 8.6821},
    "Singapore, SG":    {"lat": 1.3521,  "lon": 103.8198},
    "São Paulo, BR":    {"lat": -23.5505,"lon": -46.6333},
    "Toronto, CA":      {"lat": 43.6532, "lon": -79.3832},
}

CITY_NAMES = list(CITY_COORDS.keys())
USER_POOL  = [f"U_{str(i).zfill(4)}" for i in range(1, 21)]

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def minutes_ago(n):
    return (datetime.now(timezone.utc) - timedelta(minutes=n)).strftime("%Y-%m-%dT%H:%M:%SZ")

def make_clean_transaction():
    city = random.choice(CITY_NAMES)
    return {
        "transaction_id": f"TXN_{uuid.uuid4().hex[:8].upper()}",
        "user_id":        random.choice(USER_POOL),
        "amount_usd":     round(random.uniform(20, 4000), 2),
        "location":       city,
        "timestamp":      now_iso(),
        "previous_login": {"location": city, "time": minutes_ago(random.randint(30, 300))},
        "scenario":       "CLEAN",
    }

def make_geo_velocity_fraud():
    city_a = random.choice(CITY_NAMES)
    city_b = random.choice([c for c in CITY_NAMES if c != city_a])
    return {
        "transaction_id": f"TXN_{uuid.uuid4().hex[:8].upper()}",
        "user_id":        random.choice(USER_POOL),
        "amount_usd":     round(random.uniform(200, 5000), 2),
        "location":       city_b,
        "timestamp":      now_iso(),
        "previous_login": {"location": city_a, "time": minutes_ago(random.randint(5, 15))},
        "scenario":       "GEO_VELOCITY",
    }

def make_structuring_fraud():
    city = random.choice(CITY_NAMES)
    return {
        "transaction_id": f"TXN_{uuid.uuid4().hex[:8].upper()}",
        "user_id":        random.choice(USER_POOL),
        "amount_usd":     round(random.uniform(9000, 9999), 2),
        "location":       city,
        "timestamp":      now_iso(),
        "previous_login": {"location": city, "time": minutes_ago(random.randint(20, 120))},
        "scenario":       "STRUCTURING",
    }

def make_behavioral_fraud():
    city = random.choice(CITY_NAMES)
    return {
        "transaction_id": f"TXN_{uuid.uuid4().hex[:8].upper()}",
        "user_id":        random.choice(USER_POOL),
        "amount_usd":     round(random.uniform(40000, 95000), 2),
        "location":       city,
        "timestamp":      now_iso(),
        "previous_login": {"location": city, "time": minutes_ago(random.randint(10, 60))},
        "scenario":       "BEHAVIORAL_SPIKE",
    }

def make_ring_fraud(ring_id: str):
    users = random.sample(USER_POOL, 3)
    city  = random.choice(CITY_NAMES)
    return [
        {
            "transaction_id": f"TXN_{uuid.uuid4().hex[:8].upper()}",
            "user_id":        user,
            "amount_usd":     round(random.uniform(3100, 3300), 2),
            "location":       city,
            "timestamp":      now_iso(),
            "previous_login": {"location": city, "time": minutes_ago(random.randint(5, 30))},
            "scenario":       "RING_FRAUD",
            "ring_id":        ring_id,
        }
        for user in users
    ]

SCENARIOS = ["CLEAN","GEO_VELOCITY","STRUCTURING","BEHAVIORAL_SPIKE","RING_FRAUD"]
WEIGHTS   = [55, 15, 15, 10, 5]

def pick_transaction():
    scenario = random.choices(SCENARIOS, weights=WEIGHTS, k=1)[0]
    if scenario == "CLEAN":            return [make_clean_transaction()]
    elif scenario == "GEO_VELOCITY":   return [make_geo_velocity_fraud()]
    elif scenario == "STRUCTURING":    return [make_structuring_fraud()]
    elif scenario == "BEHAVIORAL_SPIKE": return [make_behavioral_fraud()]
    elif scenario == "RING_FRAUD":     return make_ring_fraud(uuid.uuid4().hex[:6].upper())

def send(txn: dict):
    try:
        # ── FIXED: timeout increased to 60s so LLM calls don't cut off ──
        resp   = requests.post(BACKEND_URL, json=txn, timeout=60)
        status = resp.status_code
        color  = "\033[92m" if status == 200 else "\033[91m"
        reset  = "\033[0m"
        print(f"{color}[{txn.get('scenario','?'):<18}]{reset}  "
              f"{txn['transaction_id']}  "
              f"user={txn['user_id']}  "
              f"${txn['amount_usd']:>10,.2f}  "
              f"loc={txn['location']:<18}  "
              f"HTTP {status}")
    except requests.exceptions.ConnectionError:
        print(f"\033[91m[CONNECTION ERROR]\033[0m  Backend not running at {BACKEND_URL}")
    except requests.exceptions.Timeout:
        print(f"\033[93m[TIMEOUT]\033[0m  {txn['transaction_id']} — backend still processing (LLM call). Will continue.")
    except Exception as e:
        print(f"\033[91m[ERROR]\033[0m  {e}")

def main():
    print("\033[1m\033[94m")
    print("=" * 72)
    print("   AML AUDITOR — Transaction Simulator")
    print("   Firing transactions every 5 seconds → " + BACKEND_URL)
    print("=" * 72)
    print("\033[0m")
    print(f"  {'SCENARIO':<22} {'TXN ID':<16} {'USER':<8} {'AMOUNT':>12}  LOCATION")
    print("  " + "-" * 68)

    while True:
        transactions = pick_transaction()
        for txn in transactions:
            send(txn)
        time.sleep(5)   # ── FIXED: 5s gap so backend has time to breathe

if __name__ == "__main__":
    main()