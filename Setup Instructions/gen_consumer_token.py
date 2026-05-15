"""
gen_consumer_token.py - Consumer iSHARE JWT (για Keyrock authentication)
Τρέξε: python3 gen_consumer_token.py
"""
import jwt, time, uuid, re
from cryptography.hazmat.primitives.serialization import load_pem_private_key

CONSUMER_EORI = 'EU.EORI.NLPLEGMACONSUMER'
PROVIDER_EORI  = 'EU.EORI.NLPLEGMA'

key = open('/iShare/consumer.key', 'rb').read()
private_key = load_pem_private_key(key, password=None)

cert_data = open('/iShare/consumer_fullchain.pem', 'rb').read().decode()
certs = re.findall(r'-----BEGIN CERTIFICATE-----\n(.*?)\n-----END CERTIFICATE-----', cert_data, re.DOTALL)
x5c = [''.join(c.split()) for c in certs]

now = int(time.time())
payload = {
    'iss': CONSUMER_EORI,
    'sub': CONSUMER_EORI,
    'aud': PROVIDER_EORI,
    'jti': str(uuid.uuid4()),
    'iat': now,
    'exp': now + 30
}
token = jwt.encode(payload, private_key, algorithm='RS256', headers={'x5c': x5c})
print(token)
