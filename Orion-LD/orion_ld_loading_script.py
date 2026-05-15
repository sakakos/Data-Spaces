"""
orion_ld_loading_script.py
==========================

Φορτώνει το Plegma dataset στον Orion-LD.

Ρύθμιση USE_AUTH:
  True  → στέλνει μέσω Kong με iSHARE JWT (για production με PEP)
  False → στέλνει απευθείας στον Orion χωρίς authentication (για PoC/dev)

Εκτέλεση:
  python orion_ld_loading_script.py

Προαπαιτούμενα:
  pip install pandas requests PyJWT cryptography
  Δημιουργία sdm_context_merged.json (μία φορά):
    python -c "
    import urllib.request, json
    urls = [
        'https://raw.githubusercontent.com/smart-data-models/dataModel.Energy/master/context.jsonld',
        'https://raw.githubusercontent.com/smart-data-models/dataModel.Building/master/context.jsonld',
        'https://raw.githubusercontent.com/smart-data-models/dataModel.Device/master/context.jsonld',
        'https://raw.githubusercontent.com/smart-data-models/dataModel.Weather/master/context.jsonld',
    ]
    merged = {}
    for url in urls:
        with urllib.request.urlopen(url) as r:
            data = json.loads(r.read())
        ctx = data.get('@context', data)
        if isinstance(ctx, list):
            for item in ctx:
                if isinstance(item, dict): merged.update(item)
        elif isinstance(ctx, dict):
            merged.update(ctx)
    json.dump(merged, open('sdm_context_merged.json', 'w'), indent=2)
    print('OK, terms:', len(merged))
    "
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# ── Ρυθμίσεις ────────────────────────────────────────────────────────────────

# True  = μέσω Kong/PEP με iSHARE JWT
# False = απευθείας στον Orion, χωρίς authentication
USE_AUTH = False

ORION_URL = "http://localhost:1026/ngsi-ld/v1/entities"
KONG_URL  = "http://localhost:8000/ngsi-ld/v1/entities"
BASE_URL  = KONG_URL if USE_AUTH else ORION_URL

# iSHARE certificates — χρειάζονται μόνο αν USE_AUTH = True
ISHARE_DIR    = "../Kong/iShare"
KEY_FILE      = f"{ISHARE_DIR}/client.key"
CERT_FILE     = f"{ISHARE_DIR}/fullchain.pem"
PROVIDER_EORI = "EU.EORI.NLPLEGMA"

BASE_DIR    = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR.parent / "Clean_Dataset"

# ── Inline @context ───────────────────────────────────────────────────────────
# Συνδυασμός:
#   1. Smart Data Models terms (από sdm_context_merged.json)
#      Καλύπτει: dateObserved, category, controlledProperty, temperature κλπ.
#   2. Plegma-specific terms — custom URIs για τα δικά μας πεδία
#      Το URI δεν χρειάζεται να "υπάρχει" — είναι globally unique identifier.
# Ο Orion-LD δεν χρειάζεται να κατεβάσει τίποτα (όλα inline).

PLEGMA_NS = "https://plegma.example.org/vocab#"

_SDM_CONTEXT_FILE = BASE_DIR / "sdm_context_merged.json"
if not _SDM_CONTEXT_FILE.exists():
    raise FileNotFoundError(
        f"Δεν βρέθηκε το {_SDM_CONTEXT_FILE}.\n"
        "Δημιούργησέ το με την εντολή που περιγράφεται στο docstring."
    )
_SDM_TERMS = json.loads(_SDM_CONTEXT_FILE.read_text(encoding="utf-8"))

_PLEGMA_TERMS = {
    # Entity types
    "HouseholdElectricMeasurement": f"{PLEGMA_NS}HouseholdElectricMeasurement",
    "EnvironmentalMeasurement":     f"{PLEGMA_NS}EnvironmentalMeasurement",
    # Properties
    "activePower":             f"{PLEGMA_NS}activePower",
    "phaseVoltage":            f"{PLEGMA_NS}phaseVoltage",
    "current":                 f"{PLEGMA_NS}current",
    "appliancePower":          f"{PLEGMA_NS}appliancePower",
    "dataQualityIssue":        f"{PLEGMA_NS}dataQualityIssue",
    "indoorTemperature":       f"{PLEGMA_NS}indoorTemperature",
    "indoorHumidity":          f"{PLEGMA_NS}indoorHumidity",
    "outdoorTemperature":      f"{PLEGMA_NS}outdoorTemperature",
    "outdoorHumidity":         f"{PLEGMA_NS}outdoorHumidity",
    "ratedWattage":            f"{PLEGMA_NS}ratedWattage",
    "detectionThreshold":      f"{PLEGMA_NS}detectionThreshold",
    "minOnDuration":           f"{PLEGMA_NS}minOnDuration",
    "minOffDuration":          f"{PLEGMA_NS}minOffDuration",
    "applianceType":           f"{PLEGMA_NS}applianceType",
    "occupancyStatus":         f"{PLEGMA_NS}occupancyStatus",
    "heatingSystem":           f"{PLEGMA_NS}heatingSystem",
    "waterHeaterType":         f"{PLEGMA_NS}waterHeaterType",
    "hasSolarPanels":          f"{PLEGMA_NS}hasSolarPanels",
    "lastRenovationYear":      f"{PLEGMA_NS}lastRenovationYear",
    "ageBand":                 f"{PLEGMA_NS}ageBand",
    "householdSize":           f"{PLEGMA_NS}householdSize",
    "familyMonthlyIncomeBand": f"{PLEGMA_NS}familyMonthlyIncomeBand",
    "individualIncomeBand":    f"{PLEGMA_NS}individualIncomeBand",
    # Relationships — plain URI (χωρίς @type: @id, ασύμβατο με NGSI-LD)
    "refBuilding":  f"{PLEGMA_NS}refBuilding",
    "hasOccupant":  f"{PLEGMA_NS}hasOccupant",
    "hasAppliance": f"{PLEGMA_NS}hasAppliance",
    "livesIn":      f"{PLEGMA_NS}livesIn",
    "installedIn":  f"{PLEGMA_NS}installedIn",
}

# Τα Plegma terms έχουν προτεραιότητα (update τελευταία)
CONTEXT = {**_SDM_TERMS, **_PLEGMA_TERMS}


# ── iSHARE JWT (μόνο αν USE_AUTH = True) ─────────────────────────────────────
def get_ishare_token() -> str:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    import jwt as pyjwt

    private_key = load_pem_private_key(open(KEY_FILE, "rb").read(), password=None)
    cert_data   = open(CERT_FILE, "rb").read().decode()
    certs = re.findall(
        r"-----BEGIN CERTIFICATE-----\n(.*?)\n-----END CERTIFICATE-----",
        cert_data, re.DOTALL,
    )
    x5c = ["".join(c.split()) for c in certs]
    now = int(time.time())
    payload = {
        "iss": PROVIDER_EORI, "sub": PROVIDER_EORI, "aud": PROVIDER_EORI,
        "jti": str(uuid.uuid4()), "iat": now, "exp": now + 30,
    }
    return pyjwt.encode(payload, private_key, algorithm="RS256", headers={"x5c": x5c})


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _headers() -> dict:
    h = {"Content-Type": "application/ld+json"}
    if USE_AUTH:
        h["Authorization"] = f"Bearer {get_ishare_token()}"
    return h


def _post(entity: dict) -> None:
    resp = requests.post(BASE_URL, data=json.dumps(entity), headers=_headers())
    label = f"{entity['type'].split('#')[-1]}  {entity['id'].split(':')[-1]}"
    if resp.status_code == 201:
        print(f"  ✓  {label}")
    elif resp.status_code == 409:
        print(f"  =  {label}  (ήδη υπάρχει)")
    else:
        print(f"  ✗  {label}: {resp.status_code} — {resp.text[:200]}")


# ── Διαγραφή όλων των entities ────────────────────────────────────────────────
# Χρησιμοποιεί το /types endpoint για να βρει δυναμικά όλους τους τύπους
# και κάνει paginated DELETE ανά τύπο.

def purge_all() -> None:
    print("\n── Διαγραφή παλιών δεδομένων ───────────────────────")
    # Βρες δυναμικά όλους τους τύπους που υπάρχουν
    types_url = ORION_URL.replace("/entities", "/types")
    resp = requests.get(types_url, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        print(f"  ✗  Αδυναμία ανάκτησης types: {resp.status_code}")
        return
    types = resp.json().get("typeList", [])

    total = 0
    for entity_type in types:
        offset = 0
        while True:
            r = requests.get(
                ORION_URL,
                params={"type": entity_type, "limit": 100, "offset": offset},
                headers={"Accept": "application/json"},
            )
            if r.status_code != 200:
                break
            entities = r.json()
            if not entities:
                break
            for e in entities:
                h = {}
                if USE_AUTH:
                    h["Authorization"] = f"Bearer {get_ishare_token()}"
                d = requests.delete(f"{ORION_URL}/{e['id']}", headers=h)
                if d.status_code == 204:
                    total += 1
            if len(entities) < 100:
                break
            offset += 100

    print(f"  ✓  Διαγράφηκαν {total} entities.")


# ── Βοηθητικές συναρτήσεις ────────────────────────────────────────────────────
def prop(value, unit_code: str = None, observed_at: str = None) -> dict:
    out = {"type": "Property", "value": value}
    if unit_code:   out["unitCode"]   = unit_code
    if observed_at: out["observedAt"] = observed_at
    return out


def rel(target: str | list[str]) -> dict:
    return {"type": "Relationship", "object": target}


def to_float(value) -> Optional[float]:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ts_to_iso(raw: str) -> str:
    """'2022-07-15 00:00:00' → '2022-07-15T00:00:00Z'"""
    iso = str(raw).strip().replace(" ", "T")
    if not iso.endswith("Z") and "+" not in iso:
        iso += "Z"
    return iso


# ── URN builders ──────────────────────────────────────────────────────────────
def building_urn(h: int) -> str:
    return f"urn:ngsi-ld:Building:House{h:02d}"

def person_urn(h: int) -> str:
    return f"urn:ngsi-ld:Person:House{h:02d}:Occupant"

def device_urn(h: int, appliance: str) -> str:
    return f"urn:ngsi-ld:Device:House{h:02d}:{appliance}"

def electric_urn(h: int, ts_iso: str) -> str:
    return f"urn:ngsi-ld:HouseholdElectricMeasurement:House{h:02d}:{ts_iso}"

def environmental_urn(h: int, ts_iso: str) -> str:
    return f"urn:ngsi-ld:EnvironmentalMeasurement:House{h:02d}:{ts_iso}"


# ── Appliance taxonomy (από Metadata_H1.txt + appliances_metadata.csv) ───────
APPLIANCE_META = {
    "ac_1":            {"applianceType": "airConditioner", "category": ["hvac"],      "location": "Living room"},
    "ac_2":            {"applianceType": "airConditioner", "category": ["hvac"],      "location": "Bedroom"},
    "boiler":          {"applianceType": "waterBoiler",    "category": ["appliance"], "location": None},
    "fridge":          {"applianceType": "fridge",         "category": ["appliance"], "location": None},
    "washing_machine": {"applianceType": "washingMachine", "category": ["appliance"], "location": None},
}


# ── Entity creators ───────────────────────────────────────────────────────────
def create_building(house_id: int, attrs: dict = None) -> None:
    """
    Δημιουργεί το static Building entity.
    attrs: dict από το xlsx metadata (category, dateOfConstruction κλπ.)
    """
    attrs = attrs or {}
    entity = {
        "id":          building_urn(house_id),
        "type":        "Building",
        "category":    prop(attrs.get("category", ["residential"])),
        "hasOccupant": rel(person_urn(house_id)),
        "@context":    CONTEXT,
    }
    for key in ("dateOfConstruction", "lastRenovationYear", "numberOfRooms",
                "occupancyStatus", "heatingSystem", "waterHeaterType", "hasSolarPanels"):
        if attrs.get(key) is not None:
            entity[key] = prop(attrs[key])
    _post(entity)


def create_person(house_id: int, attrs: dict = None) -> None:
    """
    Δημιουργεί το static Person entity (anonymized sociodemographic).
    attrs: dict από το xlsx metadata (gender, ageBand κλπ.)
    """
    attrs = attrs or {}
    entity = {
        "id":       person_urn(house_id),
        "type":     "Person",
        "livesIn":  rel(building_urn(house_id)),
        "@context": CONTEXT,
    }
    for key in ("gender", "ageBand", "occupation", "educationLevel",
                "householdSize", "familyMonthlyIncomeBand", "individualIncomeBand", "pets"):
        if attrs.get(key) is not None:
            entity[key] = prop(attrs[key])
    _post(entity)


def create_devices(house_id: int) -> list[str]:
    """
    Διαβάζει appliances_metadata.csv και δημιουργεί ένα Device entity
    ανά συσκευή. Επιστρέφει τη λίστα URNs για το link στο Building.
    """
    csv_path = (
        DATASET_DIR / f"House_{house_id:02d}"
        / "Electric_data" / "appliances_metadata.csv"
    )
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    created_urns = []
    for _, row in df.iterrows():
        appliance = row["appliance"].strip()
        meta = APPLIANCE_META.get(appliance, {
            "applianceType": "other", "category": ["appliance"], "location": None,
        })
        entity = {
            "id":                 device_urn(house_id, appliance),
            "type":               "Device",
            "category":           prop(meta["category"]),
            "controlledProperty": prop(["power"]),
            "applianceType":      prop(meta["applianceType"]),
            "ratedWattage":       prop(to_float(row["wattage [W]"]),   "WTT"),
            "detectionThreshold": prop(to_float(row["threshold [W]"]), "WTT"),
            "installedIn":        rel(building_urn(house_id)),
            "@context":           CONTEXT,
        }
        if meta.get("location"):
            entity["location"] = prop(meta["location"])
        min_on  = to_float(row.get("min_on (sec)"))
        min_off = to_float(row.get("min_off (sec)"))
        if min_on  is not None: entity["minOnDuration"]  = prop(min_on,  "SEC")
        if min_off is not None: entity["minOffDuration"] = prop(min_off, "SEC")

        _post(entity)
        created_urns.append(entity["id"])
    return created_urns


def link_appliances_to_building(house_id: int, device_urns: list[str]) -> None:
    """
    Προσθέτει το hasAppliance relationship στο Building.
    Χρησιμοποιεί POST /attrs (όχι PATCH) γιατί το attribute δεν υπάρχει ακόμα.
    """
    url = f"{ORION_URL}/{building_urn(house_id)}/attrs"
    body = {
        "hasAppliance": rel(device_urns),
        "@context":     CONTEXT,
    }
    headers = {"Content-Type": "application/ld+json"}
    if USE_AUTH:
        headers["Authorization"] = f"Bearer {get_ishare_token()}"
    resp = requests.post(url, data=json.dumps(body), headers=headers)
    if resp.status_code in (204, 207):
        print("  ~  hasAppliance linked: OK")
    else:
        print(f"  ~  hasAppliance: {resp.status_code} — {resp.text[:200]}")


# ── Time-series ingestion ─────────────────────────────────────────────────────
ELECTRIC_APPLIANCES = ["ac_1", "ac_2", "boiler", "fridge", "washing_machine"]


def ingest_electric_data(house_id: int, month: str, limit: int = None) -> None:
    """
    Φορτώνει ένα μηνιαίο Electric_data CSV.
    Στήλες: timestamp, V, A, P_agg, ac_1, ac_2, boiler, fridge,
            washing_machine, issues
    """
    csv_path = (
        DATASET_DIR / f"House_{house_id:02d}"
        / "Electric_data" / f"{month}.csv"
    )
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if limit:
        df = df.head(limit)

    print(f"\n  Electric  House_{house_id:02d}/{month}.csv  ({len(df)} rows)")
    for _, row in df.iterrows():
        ts = ts_to_iso(row["timestamp"])
        entity = {
            "id":   electric_urn(house_id, ts),
            "type": "HouseholdElectricMeasurement",
            "dateObserved": {
                "type":  "Property",
                "value": {"@type": "DateTime", "@value": ts},
            },
            "refBuilding": rel(building_urn(house_id)),
            "@context":    CONTEXT,
        }
        p = to_float(row.get("P_agg"))
        v = to_float(row.get("V"))
        a = to_float(row.get("A"))
        if p is not None: entity["activePower"]  = prop(p, "WTT", ts)
        if v is not None: entity["phaseVoltage"] = prop(v, "VLT", ts)
        if a is not None: entity["current"]      = prop(a, "AMP", ts)

        # Appliance-level readings — inline dict
        # Κλειδί = suffix του Device URN (ac_1 → urn:ngsi-ld:Device:HouseXX:ac_1)
        appliance_power = {}
        for key in ELECTRIC_APPLIANCES:
            val = to_float(row.get(key))
            if val is not None:
                appliance_power[key] = val
        if appliance_power:
            entity["appliancePower"] = prop(appliance_power, "WTT", ts)

        if "issues" in df.columns and not pd.isna(row.get("issues")):
            entity["dataQualityIssue"] = prop(bool(int(row["issues"])))

        _post(entity)


def ingest_environmental_data(house_id: int, month: str, limit: int = None) -> None:
    """
    Φορτώνει ένα μηνιαίο Environmental_data CSV.
    Στήλες: timestamp, internal_temperature, internal_humidity,
            external_temperature, external_humidity
    """
    csv_path = (
        DATASET_DIR / f"House_{house_id:02d}"
        / "Environmental_data" / f"{month}.csv"
    )
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if limit:
        df = df.head(limit)

    print(f"\n  Environmental  House_{house_id:02d}/{month}.csv  ({len(df)} rows)")
    COLUMN_MAP = {
        "internal_temperature": ("indoorTemperature",  "CEL"),
        "internal_humidity":    ("indoorHumidity",     "P1"),
        "external_temperature": ("outdoorTemperature", "CEL"),
        "external_humidity":    ("outdoorHumidity",    "P1"),
    }
    for _, row in df.iterrows():
        ts = ts_to_iso(row["timestamp"])
        entity = {
            "id":   environmental_urn(house_id, ts),
            "type": "EnvironmentalMeasurement",
            "dateObserved": {
                "type":  "Property",
                "value": {"@type": "DateTime", "@value": ts},
            },
            "refBuilding": rel(building_urn(house_id)),
            "@context":    CONTEXT,
        }
        for csv_col, (ngsi_key, unit) in COLUMN_MAP.items():
            val = to_float(row.get(csv_col))
            if val is not None:
                entity[ngsi_key] = prop(val, unit, ts)

        if "issues" in df.columns and not pd.isna(row.get("issues")):
            entity["dataQualityIssue"] = prop(bool(int(row["issues"])))

        _post(entity)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    HOUSE_ID = 1
    MONTH    = "2022-07"
    LIMIT    = 10   # None για όλες τις γραμμές του μήνα

    # Metadata από το xlsx (συμπλήρωσε χειροκίνητα ανά σπίτι)
    building_attrs = {
        "category":           ["residential", "apartment"],
        "dateOfConstruction": "1950/1970",
        "numberOfRooms":      3,
        "occupancyStatus":    "renter",
        "heatingSystem":      ["radiatorOil", "airConditioner"],
        "waterHeaterType":    "electricBoiler",
        "hasSolarPanels":     False,
    }
    person_attrs = {
        "gender":                  "male",
        "ageBand":                 "25-30",
        "educationLevel":          "doctorateDegree",
        "householdSize":           {"adults": 2},
        "familyMonthlyIncomeBand": "fourToSixWages",
    }

    print("=" * 55)
    print(f"  Plegma → Orion-LD   House {HOUSE_ID:02d}  /  {MONTH}")
    print(f"  Mode: {'Kong/PEP (auth)' if USE_AUTH else 'Direct Orion (no auth)'}")
    print("=" * 55)

    purge_all()

    print("\n── Static entities ─────────────────────────────────")
    create_building(HOUSE_ID, building_attrs)
    create_person(HOUSE_ID, person_attrs)
    device_urns = create_devices(HOUSE_ID)
    link_appliances_to_building(HOUSE_ID, device_urns)

    print("\n── Time-series ─────────────────────────────────────")
    ingest_electric_data(HOUSE_ID, MONTH, limit=LIMIT)
    ingest_environmental_data(HOUSE_ID, MONTH, limit=LIMIT)

    print("\n✓  Ολοκληρώθηκε.")
