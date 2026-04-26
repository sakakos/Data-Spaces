import pandas as pd
import requests
import json
from pathlib import Path

# Ρυθμίσεις
ORION_URL = "http://localhost:1026/ngsi-ld/v1/entities"
CONTEXT_URL = "https://raw.githubusercontent.com/smart-data-models/dataModel.Energy/master/context.jsonld"

BASE_DIR = Path(__file__).resolve().parent


def _to_float_or_none(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _add_property_if_value(entity, key, value):
    if value is not None:
        entity[key] = {"type": "Property", "value": value}

def ingest_data(file_path, house_id, limit=5):
    # Αν δοθεί μόνο όνομα αρχείου, φτιάξε το μονοπάτι βάσει της δομής φακέλων.
    csv_path = Path(file_path)
    if not csv_path.is_absolute() and len(csv_path.parts) == 1:
        csv_path = (
            BASE_DIR
            / "Clean_Dataset"
            / f"House_{house_id:02d}"
            / "Electric_data"
            / csv_path
        )

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found: {csv_path}. "
            "Expected either an absolute path or a file under "
            f"Clean_Dataset/House_{house_id:02d}/Electric_data/."
        )

    # Διάβασμα του CSV
    df = pd.read_csv(csv_path)

    # Ενοποίηση ονομάτων στηλών ώστε να δουλεύει με διαφορετικά datasets.
    df = df.rename(columns=str.strip)
    lower_to_actual = {col.lower(): col for col in df.columns}

    def col(name, fallback=None):
        return lower_to_actual.get(name.lower(), fallback)

    timestamp_col = col("timestamp")
    p_agg_col = col("p_agg")
    voltage_col = col("voltage") or col("v")
    temp_col = col("temp_internal")
    humidity_col = col("hum_internal")
    fridge_col = col("fridge")
    washing_machine_col = col("washing_machine")
    issues_col = col("issues")
    ac_col = col("ac")
    ac1_col = col("ac_1")
    ac2_col = col("ac_2")

    required_columns = [
        ("timestamp", timestamp_col),
        ("p_agg", p_agg_col),
        ("voltage or v", voltage_col),
    ]
    missing_required = [name for name, found in required_columns if found is None]
    if missing_required:
        raise KeyError(
            "Missing required columns: "
            + ", ".join(missing_required)
            + f". Available columns: {list(df.columns)}"
        )
    
    # Επιλογή μόνο των πρώτων γραμμών για το Proof of Concept (Week 1)
    df = df.head(limit)

    for index, row in df.iterrows():
        timestamp_value = str(row[timestamp_col]).strip()
        active_power_value = _to_float_or_none(row[p_agg_col])
        voltage_value = _to_float_or_none(row[voltage_col])
        internal_temperature_value = _to_float_or_none(row[temp_col]) if temp_col is not None else None
        internal_humidity_value = _to_float_or_none(row[humidity_col]) if humidity_col is not None else None
        fridge_value = _to_float_or_none(row[fridge_col]) if fridge_col is not None else None
        washing_machine_value = _to_float_or_none(row[washing_machine_col]) if washing_machine_col is not None else None

        if ac_col is not None:
            ac_value = _to_float_or_none(row[ac_col])
        else:
            ac_part_1 = _to_float_or_none(row[ac1_col]) if ac1_col is not None else 0.0
            ac_part_2 = _to_float_or_none(row[ac2_col]) if ac2_col is not None else 0.0
            ac_value = (ac_part_1 or 0.0) + (ac_part_2 or 0.0)

        # Δημιουργία του NGSI-LD payload
        entity = {
            "id": f"urn:ngsi-ld:HouseholdMeasurement:House{house_id}:{timestamp_value.replace(' ', 'T')}",
            "type": "HouseholdMeasurement",
            "dateObserved": {"type": "Property", "value": timestamp_value},
            "aggregateActivePower": {"type": "Property", "value": active_power_value},
            "aggregateVoltage": {"type": "Property", "value": voltage_value},
            "dataQualityIssue": {
                "type": "Property",
                "value": bool(int(row[issues_col])) if issues_col is not None and not pd.isna(row[issues_col]) else False,
            },
            "@context": CONTEXT_URL
        }

        _add_property_if_value(entity, "internalTemperature", internal_temperature_value)
        _add_property_if_value(entity, "internalHumidity", internal_humidity_value)

        appliance_power = {}
        if ac_value is not None:
            appliance_power["ac"] = ac_value
        if fridge_value is not None:
            appliance_power["fridge"] = fridge_value
        if washing_machine_value is not None:
            appliance_power["washing_machine"] = washing_machine_value

        if appliance_power:
            entity["appliancePower"] = {"type": "Property", "value": appliance_power}

        # Αποστολή στον Orion
        headers = {"Content-Type": "application/ld+json"}
        response = requests.post(ORION_URL, data=json.dumps(entity), headers=headers)
        
        if response.status_code == 201:
            print(f"Row {index} ingested successfully.")
        else:
            print(f"Failed row {index}: {response.status_code} - {response.text}")

# Εκτέλεση για το αρχείο 2022-07.csv του House 1
ingest_data('2022-07.csv', house_id=1, limit=10)