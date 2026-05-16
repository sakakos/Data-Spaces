# demo.ps1
# =========================================================
# Επίδειξη ελέγχου πρόσβασης μέσω Kong/PEP με iSHARE JWT
#
# Σενάριο 1: Χωρίς token        → 401 Unauthorized
# Σενάριο 2: Provider token      → 200 OK + δεδομένα
# =========================================================

$ISHARE_DIR = "C:\Users\SAKak\Documents\GitHub\Data-Spaces\Kong\iShare"
$KONG_BASE  = "http://localhost:8000/ngsi-ld/v1/entities"

# Τα entity types πρέπει να δίνονται ως πλήρη URIs
# (ο Orion-LD τα αποθηκεύει έτσι λόγω inline @context)
$ELECTRIC_TYPE = "https://plegma.example.org/vocab%23HouseholdElectricMeasurement"
$ENV_TYPE      = "https://plegma.example.org/vocab%23EnvironmentalMeasurement"
$BUILDING_TYPE = "https://smartdatamodels.org/dataModel.Building/Building"

Write-Host "============================================================"
Write-Host "  Plegma Data Space — Demo Ελέγχου Πρόσβασης"
Write-Host "============================================================"

# 1. Χωρίς token — πρέπει 401
Write-Host "`n=== 1. Χωρίς token (αναμενόμενο: 401) ==="
curl.exe -s "$KONG_BASE`?type=$ELECTRIC_TYPE&limit=1"

# 2. Provider token — παράγουμε φρέσκο JWT και στέλνουμε request
Write-Host "`n=== 2. Provider token (αναμενόμενο: 200) ==="
$PROVIDER_TOKEN = docker run --rm `
    -v "${ISHARE_DIR}:/iShare" `
    python:3.9-slim sh -c `
    "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_token.py"

Write-Host "HouseholdElectricMeasurement:"
curl.exe -s -H "Authorization: Bearer $PROVIDER_TOKEN" `
    "$KONG_BASE`?type=$ELECTRIC_TYPE&limit=1" | python -m json.tool

Write-Host "`nEnvironmentalMeasurement:"
curl.exe -s -H "Authorization: Bearer $PROVIDER_TOKEN" `
    "$KONG_BASE`?type=$ENV_TYPE&limit=1" | python -m json.tool

Write-Host "`nBuilding:"
curl.exe -s -H "Authorization: Bearer $PROVIDER_TOKEN" `
    "$KONG_BASE`?type=$BUILDING_TYPE&limit=1" | python -m json.tool
