from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PrivateFormat, NoEncryption

key = load_pem_private_key(open('/iShare/client.key', 'rb').read(), password=None)
rsa_pem = key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
open('/iShare/client_rsa.key', 'wb').write(rsa_pem)
print(rsa_pem.decode()[:30])
print('Done')
