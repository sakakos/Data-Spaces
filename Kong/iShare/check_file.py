with open('/iShare/test_entity.json', 'rb') as f:
    data = f.read()
print('First bytes hex:', data[:10].hex())
print('Content start:', data[:50])
