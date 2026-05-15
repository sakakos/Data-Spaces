entity = '{"id":"urn:ngsi-ld:HouseholdMeasurement:TestHouse:2026-05-15T10:00:00","type":"HouseholdMeasurement","aggregateActivePower":{"type":"Property","value":100.5},"aggregateVoltage":{"type":"Property","value":230.0},"@context":"https://raw.githubusercontent.com/smart-data-models/dataModel.Energy/master/context.jsonld"}'
with open('/iShare/test_entity.json', 'w', encoding='utf-8') as f:
    f.write(entity)
print('Done, first bytes:', open('/iShare/test_entity.json','rb').read()[:5].hex())
