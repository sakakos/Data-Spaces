"""
demo_query.py
=============

Επίδειξη ελέγχου πρόσβασης στον Orion-LD μέσω Kong (PEP) με iSHARE JWT.

Δείχνει τρία σενάρια:
  1. Χωρίς token        → 401 Unauthorized
  2. Provider token     → 200 OK + δεδομένα
  3. Consumer token     → 200 OK (αν έχει εκχωρηθεί πρόσβαση) ή 401

Entity types (πλήρη URIs όπως αποθηκεύονται στον Orion-LD):
  HouseholdElectricMeasurement → https://plegma.example.org/vocab#HouseholdElectricMeasurement
  EnvironmentalMeasurement     → https://plegma.example.org/vocab#EnvironmentalMeasurement
  Building                     → https://smartdatamodels.org/dataModel.Building/Building
  Device                       → https://smartdatamodels.org/dataModel.Device/Device
"""

import json
import subprocess
import requests

# ── Ρυθμίσεις ────────────────────────────────────────────────────────────────
KONG_BASE  = "http://localhost:8000/ngsi-ld/v1/entities"
ISHARE_DIR = r"C:\Users\SAKak\Documents\GitHub\Data-Spaces\Kong\iShare"

# Πλήρη URIs για query (ο Orion-LD δεν έχει context για να μετατρέψει short names)
PLEGMA_NS = "https://plegma.example.org/vocab%23"   # %23 = # (URL-encoded)
TYPES = {
    "HouseholdElectricMeasurement": f"{PLEGMA_NS}HouseholdElectricMeasurement",
    "EnvironmentalMeasurement":     f"{PLEGMA_NS}EnvironmentalMeasurement",
    "Building": "https://smartdatamodels.org/dataModel.Building/Building",
    "Device":   "https://smartdatamodels.org/dataModel.Device/Device",
}


# ── Token generators ──────────────────────────────────────────────────────────
def get_provider_token() -> str:
    result = subprocess.run(
        ["docker", "run", "--rm",
         "-v", f"{ISHARE_DIR}:/iShare",
         "python:3.9-slim", "sh", "-c",
         "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_token.py"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def get_consumer_token() -> str:
    result = subprocess.run(
        ["docker", "run", "--rm",
         "-v", f"{ISHARE_DIR}:/iShare",
         "python:3.9-slim", "sh", "-c",
         "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_consumer_token.py"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


# ── Query helper ──────────────────────────────────────────────────────────────
def query(entity_type_key: str, token: str = None, limit: int = 1) -> None:
    type_uri = TYPES[entity_type_key]
    headers  = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.get(
        f"{KONG_BASE}?type={type_uri}&limit={limit}",
        headers=headers
    )

    if r.status_code == 200:
        data = r.json()
        print(f"  200 OK — {len(data)} entities")
        if data:
            # Εκτύπωσε τα βασικά πεδία του πρώτου entity
            e = data[0]
            print(f"  id: {e['id']}")
            for key, val in e.items():
                if key not in ("id", "type", "@context"):
                    short = key.split("#")[-1].split("/")[-1]
                    if isinstance(val, dict):
                        if val.get("type") == "Relationship":
                            value = f"→ {val.get('object')}"
                        else:
                            value = val.get("value")
                    else:
                        value = val
                    print(f"  {short}: {value}")
    else:
        print(f"  {r.status_code} — {r.text[:120]}")


# ── Main demo ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 60)
    print("  Plegma Data Space — Demo Ελέγχου Πρόσβασης")
    print("=" * 60)

    print("\n── 1. Χωρίς token (αναμενόμενο: 401) ──────────────────")
    query("HouseholdElectricMeasurement", token=None)

    print("\n── 2. Provider token (αναμενόμενο: 200) ───────────────")
    print("  Παραγωγή provider JWT...")
    provider_token = get_provider_token()
    print(f"  Token: {provider_token[:40]}...")

    print("\n  HouseholdElectricMeasurement:")
    query("HouseholdElectricMeasurement", token=provider_token)

    print("\n  EnvironmentalMeasurement:")
    query("EnvironmentalMeasurement", token=provider_token)

    print("\n  Building:")
    query("Building", token=provider_token)

    print("\n  Device:")
    query("Device", token=provider_token)

    print("\n── 3. Consumer token (αναμενόμενο: 200 ή 401) ─────────")
    print("  Παραγωγή consumer JWT...")
    consumer_token = get_consumer_token()
    if consumer_token:
        print(f"  Token: {consumer_token[:40]}...")
        query("HouseholdElectricMeasurement", token=consumer_token)
    else:
        print("  Consumer token δεν παράχθηκε.")

    print("\n✓  Demo ολοκληρώθηκε.")
