# FIWARE Data Space - Setup Guide
## Plegma Data Space με iSHARE/i4Trust

---

## Αρχιτεκτονική

```
Client → Kong:8000 (PEP) → DSBA-PDP:8080 (PDP) → iSHARE Satellite:8080 (Trust Anchor)
                                                  → Keyrock:3007 (AR + Identity)
                         → Orion-LD:1026 (Data)
```

---

## Βήμα 1: Δημιουργία Certificates

```powershell
# Τρέξε μόνο μία φορά για να δημιουργήσεις όλα τα certificates
docker run --rm -v ".\iShare:/iShare" python:3.9-slim sh -c `
  "pip install cryptography -q 2>/dev/null && python3 /iShare/01_generate_certs.py"
```

**Το script θα εκτυπώσει:**
- Fingerprints για το `satellite.yml`
- x5c string για το `kong.yml`
- CA fingerprint για το `docker-compose.yml` του DSBA-PDP

---

## Βήμα 2: Ενημέρωση Config Files

### satellite.yml
Ενημέρωσε τα `certificate_fingerprint` και `crt` για provider και consumer
με τα values από το Βήμα 1.

### kong.yml (jws section)
```yaml
jws:
  identifier: EU.EORI.NLPLEGMA
  root_ca_file: /iShare/certificate.pem
  private_key: /iShare/key.pem          # mount: client_rsa.key
  x5c: "<CERT0_B64>,<CERT1_B64>"        # από το script output
```

### docker-compose.yml (Kong service)
```yaml
volumes:
  - ./kong.yml:/usr/local/kong/declarative/kong.yml
  - ./iShare/fullchain.pem:/iShare/certificate.pem
  - ./iShare/client_rsa.key:/iShare/key.pem   # ΠΡΟΣΟΧΗ: RSA format!
```

### docker-compose.yml (DSBA-PDP)
```yaml
environment:
  - ISHARE_TRUSTED_FINGERPRINTS_LIST=<CA_FINGERPRINT>  # από script output
```

### Keyrock docker-compose.yml
```yaml
environment:
  - IDM_PR_CLIENT_ID=EU.EORI.NLPLEGMA
  - IDM_PR_ID=EU.EORI.NLPLEGMA
  - IDM_PR_URL=http://ishare-satellite:8080
  - IDM_PR_TOKEN_ENDPOINT=http://ishare-satellite:8080/token
  - IDM_PR_PARTIES_ENDPOINT=http://ishare-satellite:8080/parties
  - IDM_PR_CLIENT_KEY=/iShare/key.pem
  - IDM_PR_CLIENT_CRT=/iShare/certificate.pem
  - IDM_AR_ID=EU.EORI.NLPLEGMA
  - IDM_AR_URL=internal
  - IDM_AR_TOKEN_ENDPOINT=http://fiware-keyrock:3007/oauth2/token
  - IDM_AR_DELEGATION_ENDPOINT=http://fiware-keyrock:3007/ar/delegation
  - IDM_PDP_LEVEL=advanced
volumes:
  - ./iShare/client.key:/iShare/key.pem
  - ./iShare/fullchain.pem:/iShare/certificate.pem
  - ./model_oauth_server.js:/opt/fiware-idm/models/model_oauth_server.js
```

---

## Βήμα 3: Εκκίνηση Containers

```powershell
# Kong stack (Satellite, DSBA-PDP, Kong)
cd Kong
docker-compose up -d

# Keyrock
cd ..\Keyrock
docker-compose up -d
```

---

## Βήμα 4: Patches & Policy Setup

```powershell
# Τρέξε αφού ξεκινήσουν τα containers
docker run --rm -v ".\iShare:/iShare" python:3.9-slim sh -c `
  "pip install requests cryptography -q 2>/dev/null && python3 /iShare/02_setup_keyrock.py"
```

**ΣΗΜΑΝΤΙΚΟ:** Πριν το Βήμα 4, πρέπει να έχει δημιουργηθεί ο consumer user στο Keyrock.
Τρέξε πρώτα μία φορά το consumer token request:

```powershell
$CONSUMER_JWT = docker run --rm -v ".\iShare:/iShare" python:3.9-slim sh -c `
  "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_consumer_token.py"

curl.exe -s -X POST "http://localhost:3007/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -d "grant_type=client_credentials&scope=iSHARE&client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer&client_assertion=$CONSUMER_JWT&client_id=EU.EORI.NLPLEGMACONSUMER"
```

Μετά τρέξε το `02_setup_keyrock.py`.

---

## Βήμα 5: Test

```powershell
# Χωρίς token - πρέπει 401
curl.exe -s "http://localhost:8000/ngsi-ld/v1/entities?type=HouseholdMeasurement&limit=1"

# Provider token - πρέπει 200
$TOKEN = docker run --rm -v ".\iShare:/iShare" python:3.9-slim sh -c `
  "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_token.py"
curl.exe -s -H "Authorization: Bearer $TOKEN" `
  "http://localhost:8000/ngsi-ld/v1/entities?type=HouseholdMeasurement&limit=3"

# Consumer token - πρέπει 200
$CONSUMER_JWT = docker run --rm -v ".\iShare:/iShare" python:3.9-slim sh -c `
  "pip install PyJWT cryptography -q 2>/dev/null && python3 /iShare/gen_consumer_token.py"
$RESPONSE = curl.exe -s -X POST "http://localhost:3007/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -d "grant_type=client_credentials&scope=iSHARE&client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer&client_assertion=$CONSUMER_JWT&client_id=EU.EORI.NLPLEGMACONSUMER"
$ACCESS_TOKEN = ($RESPONSE | ConvertFrom-Json).access_token
curl.exe -s -H "Authorization: Bearer $ACCESS_TOKEN" `
  "http://localhost:8000/ngsi-ld/v1/entities?type=HouseholdMeasurement&limit=1"
```

---

## Γνωστά Προβλήματα & Λύσεις

### "signer error: no start line" στο Kong
**Αιτία:** Το Kong χρησιμοποιεί `lua-resty-jwt` που απαιτεί PKCS#1 format key.
**Λύση:** Mount το `client_rsa.key` (όχι `client.key`) στο Kong volume.

### "digitalSignature" error στο Keyrock extparticipant
**Αιτία:** Τα certificates δεν έχουν `keyUsage: digitalSignature` extension.
**Λύση:** Τα νέα certificates από το `01_generate_certs.py` το έχουν ήδη.

### "delegationEvidence: null" στο consumer token
**Αιτία:** Η delegation policy αποθηκεύτηκε με EORI αντί για UUID.
**Λύση:** Το `02_setup_keyrock.py` το διορθώνει αυτόματα.

### "invalid client credentials" στο Keyrock για provider
**Αιτία:** Το Keyrock δεν μπορεί να διαβάσει τα certificates (format ή path).
**Λύση:** Βεβαιώσου ότι τα `IDM_PR_CLIENT_KEY` και `IDM_PR_CLIENT_CRT` env vars
δείχνουν σε valid file paths και το `configService.js` patch έχει εφαρμοστεί.

---

## EORI & Identifiers

| Component | EORI |
|-----------|------|
| Provider / Satellite / Kong / DSBA-PDP | EU.EORI.NLPLEGMA |
| Consumer | EU.EORI.NLPLEGMACONSUMER |

---

## Keyrock Application Credentials
- Client ID: `ff59ca46-8155-45ac-9145-8729d47b13c3`
- Client Secret: `df2b8166-cbd9-474f-9ec6-c11a821a428d`
- Admin: `admin@test.com` / `1234`
