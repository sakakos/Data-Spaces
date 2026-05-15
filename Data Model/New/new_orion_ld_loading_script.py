"""
orion_ld_loading_script.py
==========================

Loads the Plegma dataset into Orion-LD via Kong (PEP) using NGSI-LD entities.

Entity model
------------
For each house (House_XX):

  Building (1)                    static — created once
    └─ hasOccupant ──→ Person (1) static — created once
    └─ hasAppliance ──→ Device[]  static — one per monitored appliance
                                          (ac_1, ac_2, boiler, fridge, washing_machine)

  HouseholdElectricMeasurement (N) time-series — one per CSV row
    └─ refBuilding ──→ Building
       appliancePower is an inline dict { "ac_1": 1234, "fridge": 150, ... }

  EnvironmentalMeasurement (N)    time-series — one per Environmental CSV row
    └─ refBuilding ──→ Building

Run order
---------
  1. create_building(house_id)
  2. create_person(house_id)
  3. create_devices(house_id)            # reads appliances_metadata.csv
  4. ingest_electric_data(...)           # reads Electric_data/YYYY-MM.csv
  5. ingest_environmental_data(...)      # reads Environmental_data/YYYY-MM.csv

All traffic goes through Kong (PEP) with a fresh iSHARE JWT per request.
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

# ── Configuration ────────────────────────────────────────────────────────────
KONG_URL    = "http://localhost:8000/ngsi-ld/v1/entities"
CONTEXT_URL = "https://example.org/plegma/plegma-context.jsonld"
# ^ Host this file from your own server (e.g. GitHub Pages / nginx) so
#   Orion-LD can resolve it. During local dev you can also use a
#   filesystem path served via `python -m http.server`.

# iSHARE certificates
ISHARE_DIR    = "./iShare"
KEY_FILE      = f"{ISHARE_DIR}/client.key"
CERT_FILE     = f"{ISHARE_DIR}/fullchain.pem"
PROVIDER_EORI = "EU.EORI.NLPLEGMA"

BASE_DIR    = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR.parent / "Clean_Dataset"   # adjust if needed


# ── iSHARE JWT helper (unchanged) ────────────────────────────────────────────
def get_ishare_token() -> str:
    """Generate a fresh iSHARE JWT (30s validity) for Kong/PEP auth."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    import jwt as pyjwt

    private_key = load_pem_private_key(open(KEY_FILE, "rb").read(), password=None)
    cert_data = open(CERT_FILE, "rb").read().decode()
    certs = re.findall(
        r"-----BEGIN CERTIFICATE-----\n(.*?)\n-----END CERTIFICATE-----",
        cert_data,
        re.DOTALL,
    )
    x5c = ["".join(c.split()) for c in certs]

    now = int(time.time())
    payload = {
        "iss": PROVIDER_EORI,
        "sub": PROVIDER_EORI,
        "aud": PROVIDER_EORI,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + 30,
    }
    return pyjwt.encode(payload, private_key, algorithm="RS256", headers={"x5c": x5c})


def _post(entity: dict) -> None:
    """POST one entity through Kong with a fresh iSHARE JWT."""
    headers = {
        "Content-Type":  "application/ld+json",
        "Authorization": f"Bearer {get_ishare_token()}",
    }
    resp = requests.post(KONG_URL, data=json.dumps(entity), headers=headers)
    short_id = entity["id"].split(":")[-1]
    if resp.status_code == 201:
        print(f"  + {entity['type']}/{short_id}")
    elif resp.status_code == 409:
        print(f"  = {entity['type']}/{short_id} (already exists)")
    else:
        print(f"  ! {entity['type']}/{short_id}: {resp.status_code} - {resp.text[:120]}")


# ── URN helpers ──────────────────────────────────────────────────────────────
def building_urn(house_id: int) -> str:
    return f"urn:ngsi-ld:Building:House{house_id:02d}"


def person_urn(house_id: int) -> str:
    return f"urn:ngsi-ld:Person:House{house_id:02d}:Occupant"


def device_urn(house_id: int, appliance: str) -> str:
    return f"urn:ngsi-ld:Device:House{house_id:02d}:{appliance}"


def electric_urn(house_id: int, ts_iso: str) -> str:
    return f"urn:ngsi-ld:HouseholdElectricMeasurement:House{house_id:02d}:{ts_iso}"


def environmental_urn(house_id: int, ts_iso: str) -> str:
    return f"urn:ngsi-ld:EnvironmentalMeasurement:House{house_id:02d}:{ts_iso}"


# ── Property/Relationship factories (NGSI-LD shape) ──────────────────────────
def prop(value, unit_code: Optional[str] = None, observed_at: Optional[str] = None) -> dict:
    out = {"type": "Property", "value": value}
    if unit_code:
        out["unitCode"] = unit_code
    if observed_at:
        out["observedAt"] = observed_at
    return out


def rel(target_urn: str | list[str]) -> dict:
    return {"type": "Relationship", "object": target_urn}


def to_float(value) -> Optional[float]:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── Entity builders ──────────────────────────────────────────────────────────
def create_building(house_id: int, building_attrs: Optional[dict] = None) -> None:
    """
    Create the static Building entity. `building_attrs` is a dict you fill in
    from the xlsx metadata (parse separately — too varied to automate fully).
    """
    attrs = building_attrs or {}
    entity = {
        "id":   building_urn(house_id),
        "type": "Building",
        "category": prop(attrs.get("category", ["residential", "apartment"])),
        "@context": CONTEXT_URL,
    }
    for key in (
        "dateOfConstruction", "lastRenovationYear", "numberOfRooms",
        "occupancyStatus", "heatingSystem", "waterHeaterType", "hasSolarPanels",
    ):
        if key in attrs and attrs[key] is not None:
            entity[key] = prop(attrs[key])

    entity["hasOccupant"]  = rel(person_urn(house_id))
    _post(entity)


def create_person(house_id: int, person_attrs: Optional[dict] = None) -> None:
    attrs = person_attrs or {}
    entity = {
        "id":   person_urn(house_id),
        "type": "Person",
        "@context": CONTEXT_URL,
    }
    for key in (
        "gender", "ageBand", "occupation", "educationLevel", "householdSize",
        "familyMonthlyIncomeBand", "individualIncomeBand", "pets",
    ):
        if key in attrs and attrs[key] is not None:
            entity[key] = prop(attrs[key])
    entity["livesIn"] = rel(building_urn(house_id))
    _post(entity)


# Mapping CSV appliance key -> (category, applianceType, function)
APPLIANCE_TAXONOMY = {
    "ac_1":            ("hvac",      "airConditioner",  ["hvac"]),
    "ac_2":            ("hvac",      "airConditioner",  ["hvac"]),
    "boiler":          ("appliance", "waterBoiler",     ["heating"]),
    "fridge":          ("appliance", "fridge",          ["refrigeration"]),
    "washing_machine": ("appliance", "washingMachine",  ["cleaning"]),
}

APPLIANCE_LOCATION = {
    "ac_1":            "Living room",
    "ac_2":            "Bedroom",
}


def create_devices(house_id: int) -> list[str]:
    """
    Read appliances_metadata.csv and create one Device entity per appliance.
    Returns the list of created device URNs (used by create_building's
    hasAppliance relationship if you choose to wire it after).
    """
    csv_path = DATASET_DIR / f"House_{house_id:02d}" / "Electric_data" / "appliances_metadata.csv"
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    created = []
    for _, row in df.iterrows():
        appliance = row["appliance"]
        category, app_type, function = APPLIANCE_TAXONOMY.get(
            appliance, ("appliance", "other", [])
        )

        entity = {
            "id":   device_urn(house_id, appliance),
            "type": "Device",
            "category":           prop([category]),
            "controlledProperty": prop(["power"]),
            "applianceType":      prop(app_type),
            "ratedWattage":       prop(to_float(row["wattage [W]"]),       unit_code="WTT"),
            "detectionThreshold": prop(to_float(row["threshold [W]"]),     unit_code="WTT"),
            "installedIn":        rel(building_urn(house_id)),
            "@context": CONTEXT_URL,
        }
        if function:
            entity["function"] = prop(function)
        if appliance in APPLIANCE_LOCATION:
            entity["location"] = prop(APPLIANCE_LOCATION[appliance])

        min_on  = to_float(row.get("min_on (sec)"))
        min_off = to_float(row.get("min_off (sec)"))
        if min_on is not None:
            entity["minOnDuration"]  = prop(min_on,  unit_code="SEC")
        if min_off is not None:
            entity["minOffDuration"] = prop(min_off, unit_code="SEC")

        _post(entity)
        created.append(entity["id"])

    return created


def link_building_to_appliances(house_id: int, device_urns: list[str]) -> None:
    """Patch the Building entity to add hasAppliance after Devices exist."""
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {get_ishare_token()}",
        "Link":          f'<{CONTEXT_URL}>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
    }
    patch_url = f"{KONG_URL}/{building_urn(house_id)}/attrs"
    body = {"hasAppliance": rel(device_urns)}
    resp = requests.patch(patch_url, data=json.dumps(body), headers=headers)
    print(f"  ~ Building/House{house_id:02d} hasAppliance: {resp.status_code}")


# ── Time-series ingestion ────────────────────────────────────────────────────
APPLIANCE_KEYS = ["ac_1", "ac_2", "boiler", "fridge", "washing_machine"]


def ingest_electric_data(house_id: int, month: str, limit: Optional[int] = None) -> None:
    """
    month: e.g. '2022-07'  -> reads Clean_Dataset/House_XX/Electric_data/2022-07.csv
    limit: optional row cap (handy for PoC).
    """
    csv_path = DATASET_DIR / f"House_{house_id:02d}" / "Electric_data" / f"{month}.csv"
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if limit:
        df = df.head(limit)

    print(f"Electric: House_{house_id:02d}/{month}.csv → {len(df)} rows")
    for _, row in df.iterrows():
        ts_raw = str(row["timestamp"]).strip()
        ts_iso = ts_raw.replace(" ", "T")
        if not ts_iso.endswith("Z") and "+" not in ts_iso:
            ts_iso = f"{ts_iso}Z"   # assume UTC if no tz

        entity = {
            "id":   electric_urn(house_id, ts_iso),
            "type": "HouseholdElectricMeasurement",
            "dateObserved": {
                "type":  "Property",
                "value": {"@type": "DateTime", "@value": ts_iso},
            },
            "refBuilding": rel(building_urn(house_id)),
            "@context":    CONTEXT_URL,
        }

        p_agg = to_float(row.get("P_agg"))
        v     = to_float(row.get("V"))
        a     = to_float(row.get("A"))
        if p_agg is not None: entity["activePower"] = prop(p_agg, unit_code="WTT", observed_at=ts_iso)
        if v     is not None: entity["voltage"]     = prop(v,     unit_code="VLT", observed_at=ts_iso)
        if a     is not None: entity["current"]     = prop(a,     unit_code="AMP", observed_at=ts_iso)

        # Inline appliance dict
        appliance_power = {}
        for key in APPLIANCE_KEYS:
            val = to_float(row.get(key))
            if val is not None:
                appliance_power[key] = val
        if appliance_power:
            entity["appliancePower"] = prop(appliance_power, unit_code="WTT", observed_at=ts_iso)

        if "issues" in df.columns and not pd.isna(row["issues"]):
            entity["dataQualityIssue"] = prop(bool(int(row["issues"])))

        _post(entity)


def ingest_environmental_data(house_id: int, month: str, limit: Optional[int] = None) -> None:
    csv_path = DATASET_DIR / f"House_{house_id:02d}" / "Environmental_data" / f"{month}.csv"
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if limit:
        df = df.head(limit)

    print(f"Environmental: House_{house_id:02d}/{month}.csv → {len(df)} rows")
    for _, row in df.iterrows():
        ts_raw = str(row["timestamp"]).strip()
        ts_iso = ts_raw.replace(" ", "T")
        if not ts_iso.endswith("Z") and "+" not in ts_iso:
            ts_iso = f"{ts_iso}Z"

        entity = {
            "id":   environmental_urn(house_id, ts_iso),
            "type": "EnvironmentalMeasurement",
            "dateObserved": {
                "type":  "Property",
                "value": {"@type": "DateTime", "@value": ts_iso},
            },
            "refBuilding": rel(building_urn(house_id)),
            "@context":    CONTEXT_URL,
        }

        mapping = {
            "internal_temperature": ("indoorTemperature",  "CEL"),
            "internal_humidity":    ("indoorHumidity",     "P1"),
            "external_temperature": ("outdoorTemperature", "CEL"),
            "external_humidity":    ("outdoorHumidity",    "P1"),
        }
        for csv_col, (ngsi_key, unit) in mapping.items():
            val = to_float(row.get(csv_col))
            if val is not None:
                entity[ngsi_key] = prop(val, unit_code=unit, observed_at=ts_iso)

        if "issues" in df.columns and not pd.isna(row.get("issues")):
            entity["dataQualityIssue"] = prop(bool(int(row["issues"])))

        _post(entity)


# ── Example run (PoC: just House 1, July 2022, 10 rows of each) ──────────────
if __name__ == "__main__":
    HOUSE_ID = 1
    MONTH    = "2022-07"

    # Fill in from the xlsx metadata (parse separately).
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
        "occupation":              "Data Scientist",
        "educationLevel":          "doctorateDegree",
        "householdSize":           {"adults": 2},
        "familyMonthlyIncomeBand": "fourToSixWages",
        "pets":                    ["dog"],
    }

    create_building(HOUSE_ID, building_attrs)
    create_person  (HOUSE_ID, person_attrs)
    devices = create_devices(HOUSE_ID)
    link_building_to_appliances(HOUSE_ID, devices)

    ingest_electric_data     (HOUSE_ID, MONTH, limit=10)
    ingest_environmental_data(HOUSE_ID, MONTH, limit=10)