"""
01_generate_certs.py
====================
Δημιουργεί όλα τα certificates για το FIWARE Data Space.
Τρέξε με: python3 01_generate_certs.py

Απαιτεί: pip install cryptography
"""
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime, os, re

OUTPUT_DIR = './iShare'
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROVIDER_EORI = 'EU.EORI.NLPLEGMA'
CONSUMER_EORI = 'EU.EORI.NLPLEGMACONSUMER'
CA_CN = 'PlegmaCA'

# ── 1. CA key + certificate ──────────────────────────────────────────────────
print('Generating CA key and certificate...')
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ca_subject = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, CA_CN),
    x509.NameAttribute(NameOID.SERIAL_NUMBER, PROVIDER_EORI),
])
ca_cert = (x509.CertificateBuilder()
    .subject_name(ca_subject)
    .issuer_name(ca_subject)
    .public_key(ca_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
    .sign(ca_key, hashes.SHA256()))

# Save CA
open(f'{OUTPUT_DIR}/ca.key', 'wb').write(ca_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
open(f'{OUTPUT_DIR}/ca.pem', 'wb').write(ca_cert.public_bytes(serialization.Encoding.PEM))
print(f'  CA fingerprint: {ca_cert.fingerprint(hashes.SHA256()).hex().upper()}')

# ── 2. Provider certificate ──────────────────────────────────────────────────
print('Generating provider certificate...')
provider_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
provider_subject = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, 'data-spaces-pdp'),
    x509.NameAttribute(NameOID.SERIAL_NUMBER, PROVIDER_EORI),
])
provider_cert = (x509.CertificateBuilder()
    .subject_name(provider_subject)
    .issuer_name(ca_cert.subject)
    .public_key(provider_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .add_extension(x509.KeyUsage(
        digital_signature=True, key_encipherment=False, content_commitment=False,
        data_encipherment=False, key_agreement=False, key_cert_sign=False,
        crl_sign=False, encipher_only=False, decipher_only=False
    ), critical=True)
    .add_extension(x509.SubjectKeyIdentifier.from_public_key(provider_key.public_key()), critical=False)
    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
    .sign(ca_key, hashes.SHA256()))

# Save provider - PKCS8 (for Python/DSBA-PDP)
open(f'{OUTPUT_DIR}/client.key', 'wb').write(provider_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
# Save provider - PKCS1/RSA (for Kong lua-resty-jwt)
open(f'{OUTPUT_DIR}/client_rsa.key', 'wb').write(provider_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
open(f'{OUTPUT_DIR}/client.pem', 'wb').write(provider_cert.public_bytes(serialization.Encoding.PEM))
# Fullchain = client + CA
open(f'{OUTPUT_DIR}/fullchain.pem', 'wb').write(
    provider_cert.public_bytes(serialization.Encoding.PEM) +
    ca_cert.public_bytes(serialization.Encoding.PEM))
provider_fp = provider_cert.fingerprint(hashes.SHA256()).hex().upper()
print(f'  Provider fingerprint: {provider_fp}')

# ── 3. Consumer certificate ───────────────────────────────────────────────────
print('Generating consumer certificate...')
consumer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
consumer_subject = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, 'data-spaces-consumer'),
    x509.NameAttribute(NameOID.SERIAL_NUMBER, CONSUMER_EORI),
])
consumer_cert = (x509.CertificateBuilder()
    .subject_name(consumer_subject)
    .issuer_name(ca_cert.subject)
    .public_key(consumer_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .add_extension(x509.KeyUsage(
        digital_signature=True, key_encipherment=False, content_commitment=False,
        data_encipherment=False, key_agreement=False, key_cert_sign=False,
        crl_sign=False, encipher_only=False, decipher_only=False
    ), critical=True)
    .sign(ca_key, hashes.SHA256()))

open(f'{OUTPUT_DIR}/consumer.key', 'wb').write(consumer_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
open(f'{OUTPUT_DIR}/consumer.pem', 'wb').write(consumer_cert.public_bytes(serialization.Encoding.PEM))
open(f'{OUTPUT_DIR}/consumer_fullchain.pem', 'wb').write(
    consumer_cert.public_bytes(serialization.Encoding.PEM) +
    ca_cert.public_bytes(serialization.Encoding.PEM))
consumer_fp = consumer_cert.fingerprint(hashes.SHA256()).hex().upper()
print(f'  Consumer fingerprint: {consumer_fp}')

# ── 4. Εκτύπωση x5c για kong.yml ─────────────────────────────────────────────
def cert_to_b64(cert):
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    lines = pem.strip().split('\n')
    return ''.join(l for l in lines if not l.startswith('---'))

provider_b64 = cert_to_b64(provider_cert)
ca_b64 = cert_to_b64(ca_cert)
ca_fp = ca_cert.fingerprint(hashes.SHA256()).hex().upper()

# ── 5. Αποτελέσματα ──────────────────────────────────────────────────────────
print('\n' + '='*60)
print('ΑΠΟΤΕΛΕΣΜΑΤΑ - Αντίγραψε αυτά στα config files:')
print('='*60)

print('\n--- satellite.yml: fingerprints section ---')
print(f'  Provider certificate_fingerprint: "{provider_fp}"')
print(f'  Consumer certificate_fingerprint: "{consumer_fp}"')
print(f'  CA fingerprint (για trusted_list): {ca_cert.fingerprint(hashes.SHA256()).hex().upper()}')

print('\n--- kong.yml: jws section ---')
print(f'  private_key: /iShare/key.pem  (mount client_rsa.key)')
print(f'  x5c: "{provider_b64},{ca_b64}"')

print('\n--- Fingerprint για DSBA-PDP env ---')
print(f'  ISHARE_TRUSTED_FINGERPRINTS_LIST={ca_fp}')

print('\nΌλα τα αρχεία αποθηκεύτηκαν στο ./iShare/')
print('Έτοιμο!')
