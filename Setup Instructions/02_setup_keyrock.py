"""
02_setup_keyrock.py
===================
Κάνει patch το Keyrock και δημιουργεί τη delegation policy για τον consumer.

Προϋποθέσεις:
- Τα containers τρέχουν (fiware-keyrock, db-mysql)
- pip install requests

Χρήση: python3 02_setup_keyrock.py
"""
import subprocess, json, requests, time, sys

KEYROCK_URL    = 'http://localhost:3007'
ADMIN_EMAIL    = 'admin@test.com'
ADMIN_PASS     = '1234'
CLIENT_ID      = 'ff59ca46-8155-45ac-9145-8729d47b13c3'
CLIENT_SECRET  = 'df2b8166-cbd9-474f-9ec6-c11a821a428d'
PROVIDER_EORI  = 'EU.EORI.NLPLEGMA'
CONSUMER_EORI  = 'EU.EORI.NLPLEGMACONSUMER'
KEYROCK_CONTAINER = 'fiware-keyrock'

# ── Patch 1: model_oauth_server.js (προσθέτει 'admin' field) ─────────────────
print('Patching model_oauth_server.js...')
patch1 = """
const fs = require('fs');
const f = '/opt/fiware-idm/models/model_oauth_server.js';
let c = fs.readFileSync(f, 'utf8');
const old = "attributes: ['id', 'username', 'email', 'description', 'website', 'gravatar', 'image', 'extra', 'eidas_id']";
const neu = "attributes: ['id', 'username', 'email', 'description', 'website', 'gravatar', 'image', 'extra', 'eidas_id', 'admin']";
if (c.includes(old)) {
  c = c.replace(old, neu);
  fs.writeFileSync(f, c);
  console.log('patch1: OK');
} else if (c.includes('admin')) {
  console.log('patch1: already applied');
} else {
  console.log('patch1: ERROR - pattern not found');
}
"""
r1 = subprocess.run(['docker', 'cp', '/dev/stdin', f'{KEYROCK_CONTAINER}:/tmp/p1.js'],
                    input=patch1.encode(), capture_output=True)
r2 = subprocess.run(['docker', 'exec', KEYROCK_CONTAINER, 'node', '/tmp/p1.js'],
                    capture_output=True, text=True)
print(f'  {r2.stdout.strip()}')

# ── Patch 2: configService.js (διαβάζει key/cert από file path) ──────────────
print('Patching configService.js...')
patch2 = """
const fs = require('fs');
const f = '/opt/fiware-idm/lib/configService.js';
let c = fs.readFileSync(f, 'utf8');
const old_key = "config.pr.client_key = process.env.IDM_PR_CLIENT_KEY;";
const neu_key = "config.pr.client_key = process.env.IDM_PR_CLIENT_KEY.startsWith('/') ? fs.readFileSync(process.env.IDM_PR_CLIENT_KEY, 'utf8') : process.env.IDM_PR_CLIENT_KEY;";
const old_crt = "config.pr.client_crt = process.env.IDM_PR_CLIENT_CRT;";
const neu_crt = "config.pr.client_crt = process.env.IDM_PR_CLIENT_CRT.startsWith('/') ? fs.readFileSync(process.env.IDM_PR_CLIENT_CRT, 'utf8') : process.env.IDM_PR_CLIENT_CRT;";
let changed = false;
if (c.includes(old_key)) { c = c.replace(old_key, neu_key); changed = true; }
if (c.includes(old_crt)) { c = c.replace(old_crt, neu_crt); changed = true; }
if (changed) {
  fs.writeFileSync(f, c);
  console.log('patch2: OK');
} else {
  console.log('patch2: already applied or pattern not found');
}
"""
r1 = subprocess.run(['docker', 'cp', '/dev/stdin', f'{KEYROCK_CONTAINER}:/tmp/p2.js'],
                    input=patch2.encode(), capture_output=True)
r2 = subprocess.run(['docker', 'exec', KEYROCK_CONTAINER, 'node', '/tmp/p2.js'],
                    capture_output=True, text=True)
print(f'  {r2.stdout.strip()}')

# ── Restart Keyrock ───────────────────────────────────────────────────────────
print('Restarting Keyrock...')
subprocess.run(['docker', 'restart', KEYROCK_CONTAINER], capture_output=True)
print('  Waiting 20s for Keyrock to start...')
time.sleep(20)

# ── Get admin token ───────────────────────────────────────────────────────────
print('Getting admin token...')
r = requests.post(f'{KEYROCK_URL}/oauth2/token',
    data={
        'grant_type': 'password',
        'username': ADMIN_EMAIL,
        'password': ADMIN_PASS,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    },
    headers={'Content-Type': 'application/x-www-form-urlencoded'})
if r.status_code != 200:
    print(f'  ERROR getting admin token: {r.text}')
    sys.exit(1)
admin_token = r.json()['access_token']
print(f'  Got token: {admin_token[:20]}...')

# ── Get consumer UUID from MySQL ──────────────────────────────────────────────
print(f'Getting UUID for {CONSUMER_EORI}...')
time.sleep(2)
r2 = subprocess.run(
    ['docker', 'exec', 'db-mysql', 'mysql', '-u', 'root', '-psecret', 'idm',
     '-e', f"SELECT id FROM user WHERE username='{CONSUMER_EORI}';"],
    capture_output=True, text=True)
lines = [l for l in r2.stdout.strip().split('\n') if l and l != 'id']
if not lines:
    print(f'  ERROR: Consumer user not found. Make sure the consumer has logged in at least once.')
    print('  Run the consumer token request first, then re-run this script.')
    sys.exit(1)
consumer_uuid = lines[0].strip()
print(f'  Consumer UUID: {consumer_uuid}')

# ── Create delegation policy ──────────────────────────────────────────────────
print('Creating delegation policy...')
policy = {
    "delegationEvidence": {
        "notBefore": 1735689600,
        "notOnOrAfter": 1798761600,
        "policyIssuer": PROVIDER_EORI,
        "target": {
            "accessSubject": consumer_uuid
        },
        "policySets": [{
            "maxDelegationDepth": 0,
            "target": {
                "environment": {
                    "licenses": ["ISHARE.0001"]
                }
            },
            "policies": [{
                "target": {
                    "resource": {
                        "type": "HouseholdMeasurement",
                        "identifiers": ["*"],
                        "attributes": ["*"]
                    },
                    "actions": ["GET"]
                },
                "rules": [{"effect": "Permit"}]
            }]
        }]
    }
}

r3 = requests.post(f'{KEYROCK_URL}/ar/policy',
    json=policy,
    headers={'Authorization': f'Bearer {admin_token}', 'Content-Type': 'application/json'})
if r3.status_code == 200:
    print('  Delegation policy created successfully!')
else:
    print(f'  ERROR: {r3.status_code} - {r3.text}')

print('\nSetup complete!')
print('You can now test with:')
print('  Provider: python3 gen_token.py')
print('  Consumer: python3 gen_consumer_token.py')
