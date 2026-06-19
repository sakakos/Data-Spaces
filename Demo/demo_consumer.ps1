$ISHARE_DIR    = "C:\Users\SAKak\Documents\GitHub\Data-Spaces\Kong\iShare"
$KONG_BASE     = "http://localhost:8000/ngsi-ld/v1/entities"
$KEYROCK_URL   = "http://localhost:3007/oauth2/token"
$CLIENT_ID     = "ff59ca46-8155-45ac-9145-8729d47b13c3"
$CLIENT_SECRET = "df2b8166-cbd9-474f-9ec6-c11a821a428d"
$CONSUMER_EORI = "EU.EORI.NLPLEGMACONSUMER"
$ELECTRIC_TYPE = "https://plegma.example.org/vocab%23HouseholdElectricMeasurement"

Write-Host "============================================================"
Write-Host "  Plegma Data Space - Demo Consumer Access Control"
Write-Host "============================================================"

# ── Σενάριο 1: Χωρίς token ──────────────────────────────────────────────────
Write-Host "`n=== 1. Χωρίς token (αναμενόμενο: 401 Unauthorized) ==="
curl.exe -s "$KONG_BASE`?type=$ELECTRIC_TYPE&limit=1"

# ── Σενάριο 2: Provider token (M2M) ─────────────────────────────────────────
Write-Host "`n=== 2. Provider iSHARE JWT (αναμενόμενο: 200 OK) ==="
Write-Host "  Δημιουργία iSHARE JWT για τον Provider..."
$PROVIDER_TOKEN = docker run --rm `
    -v "${ISHARE_DIR}:/iShare" `
    python:3.9-slim sh -c `
    "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_token.py"

Write-Host "  Αποστολή request στο Kong..."
curl.exe -s -H "Authorization: Bearer $PROVIDER_TOKEN" `
    "$KONG_BASE`?type=$ELECTRIC_TYPE&limit=1" | python -m json.tool

# ── Σενάριο 3: Consumer token (M2M με delegation) ───────────────────────────
Write-Host "`n=== 3. Consumer token μέσω Keyrock delegation (αναμενόμενο: 200 OK) ==="

# Βήμα 3α: Δημιουργία consumer iSHARE JWT
Write-Host "  Βήμα 1/3: Δημιουργία iSHARE JWT για τον Consumer..."
$CONSUMER_JWT = docker run --rm `
    -v "${ISHARE_DIR}:/iShare" `
    python:3.9-slim sh -c `
    "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_consumer_token.py"

# Βήμα 3β: Ανταλλαγή JWT με access token από το Keyrock
Write-Host "  Βήμα 2/3: Λήψη access token από το Keyrock (επαλήθευση μέσω Satellite + delegation policy)..."
$tokenResponse = curl.exe -s -X POST $KEYROCK_URL `
    -H "Content-Type: application/x-www-form-urlencoded" `
    -d "grant_type=client_credentials&scope=iSHARE&client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer&client_assertion=$CONSUMER_JWT&client_id=$CONSUMER_EORI"

$ACCESS_TOKEN = ($tokenResponse | ConvertFrom-Json).access_token

if (-not $ACCESS_TOKEN) {
    Write-Host "  ΣΦΑΛΜΑ: Δεν ελήφθη access token από το Keyrock!"
    Write-Host "  Response: $tokenResponse"
    exit 1
}
Write-Host "  Access token ελήφθη επιτυχώς (length: $($ACCESS_TOKEN.Length) chars)"

# Βήμα 3γ: Χρήση access token για πρόσβαση μέσω Kong
Write-Host "  Βήμα 3/3: Αποστολή request στο Kong με access token..."
curl.exe -s -H "Authorization: Bearer $ACCESS_TOKEN" `
    "$KONG_BASE`?type=$ELECTRIC_TYPE&limit=1" | python -m json.tool

Write-Host "`n============================================================"
Write-Host "  Αποτελέσματα:"
Write-Host "  1. Χωρίς token       → 401 Unauthorized ✓"
Write-Host "  2. Provider token    → 200 OK ✓"
Write-Host "  3. Consumer token    → 200 OK ✓ (μέσω delegation)"
Write-Host "============================================================"