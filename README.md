# Data Space

An experimentation environment for Data Spaces using [FIWARE](https://www.fiware.org/) open-source technologies and the [i4Trust](https://github.com/i4Trust)/[iSHARE](https://ishare.eu/) trust framework.

Data Spaces are decentralized environments where organizations share data while each retains full control over who can access their resources, under what conditions, and for which purpose, a principle known as digital sovereignty. Unlike centralized platforms, data never leaves the provider's infrastructure; instead, access is governed by cryptographic identity verification and explicit delegation policies.

This project implements a fully functional Data Space that demonstrates this concept end-to-end. Two hypothetical organizations participate: a data provider that publishes household energy measurements, and a data consumer that requests access to them. The provider defines fine-grained access policies specifying exactly which data types the consumer can read. Every request passes through a chain of cryptographic verification before reaching the data.

## Architecture

The system is organized into three layers, each built from open-source components that communicate via standardized protocols:

**Policy Enforcement Layer:** The Kong API Gateway acts as the sole entry point for all requests. It extracts the caller's JWT, verifies the digital signature against the X.509 certificate chain, checks the certificate authority against the Satellite's trusted list, and evaluates the embedded delegation policy before forwarding or rejecting the request. The Orion-LD Context Broker is never exposed directly.

**Trust & Identity Layer:** The iSHARE Satellite maintains the registry of approved participants and their certificate fingerprints, serving as the trust anchor of the Data Space. The Keyrock Identity Manager authenticates external organizations via iSHARE JWT tokens, stores delegation policies in its MySQL database, and issues access tokens that embed the granted permissions as delegation evidence.

**Data Layer:** The Orion-LD Context Broker stores and serves data as NGSI-LD entities, backed by MongoDB. It supports queries by entity type, temporal filters, and semantic relationships between entities.


## Data

The system uses real-world data from the [Plegma Dataset](https://github.com/sathanasoulias/Plegma-Dataset), a collection of household energy measurements from 13 homes in Greece covering approximately 15 months at one-minute resolution. The data is modeled as five interconnected NGSI-LD entity types:

```
Building ──hasOccupant ──► Person
   │
   └──hasAppliance ──► Device (×5 per household)

HouseholdElectricMeasurement ──refBuilding ──► Building
EnvironmentalMeasurement     ──refBuilding ──► Building
```

- **Building** - Household metadata: construction period, heating system, number of rooms
- **Device** - Monitored appliance: air conditioner, fridge, boiler, washing machine
- **Person** - Anonymized occupant demographics
- **HouseholdElectricMeasurement** - Per-minute readings: active power (W), voltage (V), current (A), per-appliance consumption
- **EnvironmentalMeasurement** - Indoor/outdoor temperature (°C) and humidity (%)

The data model is defined using a custom JSON-LD context aligned with the [FIWARE Smart Data Models](https://smartdatamodels.org/), ensuring semantic interoperability with other Data Spaces.

## Repository Structure

```
Data-Spaces/
│
├── Kong/                                  # Policy Enforcement Layer
│   ├── docker-compose.yml                 #   Kong + Satellite + DSBA-PDP containers
│   ├── kong.yml                           #   Declarative Kong configuration (DB-less)
│   ├── satellite.yml                      #   iSHARE participant registry + trusted CA list
│   └── iShare/                            #   Certificates, keys, and JWT scripts
│       ├── ca.pem                         #     Root CA certificate (self-signed)
│       ├── client.key / client_rsa.key    #    Provider keys (PKCS#8 / PKCS#1)
│       ├── client.pem / fullchain.pem     #     Provider certificate / full chain
│       ├── consumer.key                   #     Consumer private key
│       ├── consumer.pem                   #     Consumer certificate
│       ├── consumer_fullchain.pem         #     Consumer certificate chain
│       ├── gen_token.py                   #     Provider iSHARE JWT generator
│       └── gen_consumer_token.py          #     Consumer iSHARE JWT generator
│
├── Keyrock/                           # Trust & Identity Layer
│   ├── docker-compose.yml             #   Keyrock + MySQL containers
│   ├── policy.json                    #   Delegation policy template
│   ├── patch1.js                      #   Patch: admin attribute in OAuth query
│   ├── patch_config.js                #   Patch: file-based key loading
│   └── iShare/                        #   Certificates mounted into Keyrock
│
├── Orion-LD/                          # Data Layer
│   ├── docker-compose/                #   Compose files (common.yml + orion-ld.yml)
│   ├── .env                           #   Environment variables
│   └── orion_ld_loading_script.py     #   CSV-to-NGSI-LD data loader
│
├── Setup Instructions/                # Automation
│   ├── 01_generate_certs.py           #   PKI: CA + provider + consumer certificates
│   └── 02_setup_keyrock.py            #   Patches + consumer registration + policy
│
├── Demo/                              # Live demonstration
│   ├── demo.ps1                       #   Provider access control scenarios
│   └── demo_consumer.ps1              #   Consumer delegation cycle (3 scenarios)
│
├── Data Model/                        # NGSI-LD schemas
│   ├── Building.yaml                  #   Household entity schema
│   ├── Device.yaml                    #   Appliance entity schema
│   ├── HouseholdElectricMeasurement.yaml
│   ├── EnvironmentalMeasurement.yaml
│   ├── Person.yaml                    #   Occupant entity schema
│   └── plegma-context.jsonld          #   JSON-LD context for Linked Data
│
├── Clean_Dataset/                     # Plegma Dataset
│   └── House_01/ ... House_13/        #   CSV files per household
│
├── Architecture Overview/             # PlantUML diagrams
│   ├── 01_component_diagram.puml
│   ├── 02_provider_sequence.puml
│   ├── 03_consumer_sequence.puml
│   └── 04_data_ingestion_sequence.puml
│
└── Thesis/                            # LaTeX source
    ├── diploma_thesis.tex
    ├── chapters/
    └── ref.bib
```

## Standards

- [NGSI-LD](https://www.etsi.org/deliver/etsi_gs/CIM/001_099/009/) (ETSI GS CIM 009)  Context information management API
- [iSHARE](https://framework.ishare.eu/)  Trust framework for inter-organizational data sharing
- [OAuth 2.0](https://www.rfc-editor.org/rfc/rfc6749) (RFC 6749)  Authorization framework (Client Credentials flow)
- [JWT](https://www.rfc-editor.org/rfc/rfc7519) (RFC 7519)  Token format with RS256 digital signatures
- [X.509](https://www.rfc-editor.org/rfc/rfc5280) (RFC 5280)  Digital certificates and PKI
- [JSON-LD](https://www.w3.org/TR/json-ld11/) (W3C)  Linked Data serialization over JSON
