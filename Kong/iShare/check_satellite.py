import yaml
cfg = yaml.safe_load(open('/var/satellite/config/satellite.yml'))
parties = cfg['satellite']['parties']
print('Parties sto Satellite:')
for p in parties:
    print('  -', p['id'], '(', p['name'], ') ->', p['status'])
