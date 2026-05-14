from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime

CONSUMER_EORI = 'EU.EORI.NLPLEGMACONSUMER'
OUTPUT_DIR = '/iShare'

print('Loading CA...')
ca_key = serialization.load_pem_private_key(open(f'{OUTPUT_DIR}/ca.key', 'rb').read(), password=None)
ca_cert = x509.load_pem_x509_certificate(open(f'{OUTPUT_DIR}/ca.pem', 'rb').read())

print('Generating consumer private key...')
consumer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

print('Generating consumer certificate...')
subject = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, 'data-spaces-consumer'),
    x509.NameAttribute(NameOID.SERIAL_NUMBER, CONSUMER_EORI),
])
cert = (x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(ca_cert.subject)
    .public_key(consumer_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .add_extension(x509.KeyUsage(
        digital_signature=True,
        key_encipherment=False,
        content_commitment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=False,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False
    ), critical=True)
    .sign(ca_key, hashes.SHA256()))

print('Saving files...')
open(f'{OUTPUT_DIR}/consumer.key', 'wb').write(consumer_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
open(f'{OUTPUT_DIR}/consumer.pem', 'wb').write(cert.public_bytes(serialization.Encoding.PEM))
open(f'{OUTPUT_DIR}/consumer_fullchain.pem', 'wb').write(
    cert.public_bytes(serialization.Encoding.PEM) + open(f'{OUTPUT_DIR}/ca.pem', 'rb').read())

fp = cert.fingerprint(hashes.SHA256()).hex().upper()
print()
print('=== Consumer Organization Created ===')
print(f'EORI:        {CONSUMER_EORI}')
print(f'Fingerprint: {fp}')
print('NOTE: Update satellite.yml with new fingerprint!')
