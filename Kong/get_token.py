import jwt, time, uuid, sys, yaml
sys.path.insert(0, '/var/satellite')
from api.util.config_handler import get_private_key
from api.util.token_handler import get_x5c_chain
cfg = yaml.safe_load(open('/var/satellite/config/satellite.yml'))
sat = cfg['satellite']
crt = sat['crt'] if isinstance(sat['crt'], str) else sat['crt'][0]
now = int(time.time())
payload = {'iss': sat['id'], 'sub': sat['id'], 'aud': sat['id'], 'jti': str(uuid.uuid4()), 'iat': now, 'exp': now+30, 'client_id': sat['id']}
header = {'x5c': get_x5c_chain(crt)}
token = jwt.encode(payload, get_private_key(sat), algorithm='RS256', headers=header)
print(token)
