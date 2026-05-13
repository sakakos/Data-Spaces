import re
cert_data = open('/iShare/fullchain.pem').read()
certs = re.findall(r'-----BEGIN CERTIFICATE-----\n(.*?)\n-----END CERTIFICATE-----', cert_data, re.DOTALL)
for i,c in enumerate(certs):
    print('=== CERT', i, '===')
    print(''.join(c.split()))
