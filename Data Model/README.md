# Plegma NGSI-LD Data Model

NGSI-LD entity schemas for the Plegma household dataset, designed for use with
Orion-LD inside a FIWARE / i4Trust data space.

## File layout

```
schemas/
  Building.yaml                       static, 1 per house
  Person.yaml                         static, 1 per house
  Device.yaml                         static, 5 per house (one per appliance)
  HouseholdElectricMeasurement.yaml   time-series, 1 per CSV row
  EnvironmentalMeasurement.yaml       time-series, 1 per CSV row

context/
  plegma-context.jsonld               JSON-LD @context that maps all custom
                                      terms to URIs. Host this file on a
                                      reachable URL and set CONTEXT_URL in
                                      the loading script.

scripts/
  orion_ld_loading_script.py          end-to-end loader (Building → Person →
                                      Devices → Electric → Environmental)
```

## Why 5 entity types

NGSI-LD models data as **entities connected by `Relationship` attributes**, not
as one big nested document. Splitting along the natural seams of the dataset
gives queries like *"all measurements from houses with solar panels"* or
*"average power consumption of fridges across the dataset"* — neither of which
is expressible if everything is one entity.

```
Building ──hasOccupant──→ Person
   │
   └──hasAppliance──→ Device (×5: ac_1, ac_2, boiler, fridge, washing_machine)

HouseholdElectricMeasurement ──refBuilding──→ Building
EnvironmentalMeasurement     ──refBuilding──→ Building
```

The static entities (Building / Person / Device) are created **once per house**.
The time-series entities are created **once per CSV row** and reference the
Building by URN so the broker can join them.

## Appliance-level readings: inline dict, not separate entities

Each `HouseholdElectricMeasurement` carries an `appliancePower` property whose
value is a dict like `{ "ac_1": 1234, "fridge": 150, ... }`. The semantic link
to the actual `Device` entities is preserved through the URN convention: the
dict key (`ac_1`) matches the suffix of `urn:ngsi-ld:Device:HouseXX:ac_1`.

Rejected alternative: one extra entity per appliance per timestamp. That would
multiply entity count by ~5× (≈3.4M instead of ≈560k entities per month for
13 houses at 1-minute resolution), without adding queryability that matters
for this PoC.

## Reuse of existing Smart Data Models

The custom schemas inherit `GSMA-Commons` and follow the naming conventions of
the official models so a consumer who already understands them can read ours:

| Custom entity                  | Reference model |
|--------------------------------|------------------------------------------------|
| `Building`                     | smart-data-models / dataModel.Building         |
| `Person`                       | smart-data-models / dataModel.User             |
| `Device`                       | smart-data-models / dataModel.Device           |
| `HouseholdElectricMeasurement` | smart-data-models / dataModel.Energy           |
| `EnvironmentalMeasurement`     | smart-data-models / dataModel.Weather          |

The `@context` file pulls in the official contexts first, then overrides /
extends them with the `plegma:` namespace for terms specific to this dataset
(`appliancePower`, `indoorHumidity`, `refBuilding`, `ratedWattage`, etc.).

## Hosting the @context

Orion-LD must be able to **HTTP GET** the context URL. Options:

1. **GitHub Pages**: push `plegma-context.jsonld` to a public repo with Pages
   enabled. URL becomes `https://<user>.github.io/<repo>/plegma-context.jsonld`.
2. **Add an `nginx` service** to your docker-compose that serves the file from
   a volume. Set `CONTEXT_URL = "http://context-server/plegma-context.jsonld"`.
3. **For local testing only**: `python -m http.server 8001` in the `context/`
   folder, then use `http://host.docker.internal:8001/plegma-context.jsonld`.

Once the URL is reachable from inside the Orion-LD container, set the
`CONTEXT_URL` constant at the top of `orion_ld_loading_script.py`.

## Ingestion order (matters!)

`Relationship` targets do **not** have to exist when an entity is created —
Orion-LD does not enforce referential integrity. But for clean queries:

1. `create_building(house_id, building_attrs)`
2. `create_person(house_id, person_attrs)`
3. `create_devices(house_id)` (reads `appliances_metadata.csv`)
4. `link_building_to_appliances(house_id, device_urns)` (PATCH on Building)
5. `ingest_electric_data(house_id, month)`
6. `ingest_environmental_data(house_id, month)`

The `__main__` block at the bottom of the script does exactly this for House 1,
July 2022, with `limit=10` for PoC.

## Scaling to all 13 houses

```python
HOUSES = range(1, 14)
MONTHS = ["2022-07", "2022-08", ..., "2023-09"]

for h in HOUSES:
    create_building(h, load_building_attrs_from_xlsx(h))
    create_person(h, load_person_attrs_from_xlsx(h))
    devices = create_devices(h)
    link_building_to_appliances(h, devices)
    for m in MONTHS:
        try:
            ingest_electric_data(h, m)
            ingest_environmental_data(h, m)
        except FileNotFoundError:
            continue   # some houses don't cover all months
```

For production-scale ingestion, switch to NGSI-LD **batch operations** at
`POST /ngsi-ld/v1/entityOperations/upsert` — up to ~1000 entities per request,
ηuge speed-up over one POST per row.

## Mapping cheat-sheet (CSV column → NGSI-LD term)

### Electric_data/YYYY-MM.csv
| CSV column        | NGSI-LD term                          | Unit |
|-------------------|---------------------------------------|------|
| `timestamp`       | `dateObserved`                        | —    |
| `V`               | `voltage`                             | V    |
| `A`               | `current`                             | A    |
| `P_agg`           | `activePower`                         | W    |
| `ac_1`            | `appliancePower.ac_1`                 | W    |
| `ac_2`            | `appliancePower.ac_2`                 | W    |
| `boiler`          | `appliancePower.boiler`               | W    |
| `fridge`          | `appliancePower.fridge`               | W    |
| `washing_machine` | `appliancePower.washing_machine`      | W    |
| `issues`          | `dataQualityIssue`                    | bool |

### Environmental_data/YYYY-MM.csv
| CSV column             | NGSI-LD term         | Unit |
|------------------------|----------------------|------|
| `timestamp`            | `dateObserved`       | —    |
| `internal_temperature` | `indoorTemperature`  | °C   |
| `internal_humidity`    | `indoorHumidity`     | %    |
| `external_temperature` | `outdoorTemperature` | °C   |
| `external_humidity`    | `outdoorHumidity`    | %    |

### appliances_metadata.csv
| CSV column        | NGSI-LD term         | Unit |
|-------------------|----------------------|------|
| `appliance`       | (id suffix)          | —    |
| `wattage [W]`     | `ratedWattage`       | W    |
| `threshold [W]`   | `detectionThreshold` | W    |
| `min_on (sec)`    | `minOnDuration`      | s    |
| `min_off (sec)`   | `minOffDuration`     | s    |
