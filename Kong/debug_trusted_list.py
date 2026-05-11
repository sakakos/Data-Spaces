import sys, yaml, traceback
sys.path.insert(0, '/var/satellite')
from flask import Flask
from api.trusted_list import trusted_list
import jwt as pyjwt, time, uuid
from api.util.token_handler import get_x5c_chain

cfg = yaml.safe_load(open('/var/satellite/config/satellite.yml'))
sat = cfg['satellite']

app = Flask(__name__)
app.config['satellite'] = sat
app.register_blueprint(trusted_list)
app.debug = True

ca_crt = sat['crt']
client_crt = open('/var/satellite/client.pem').read()
client_key = open('/var/satellite/client.key').read()
combined = client_crt + ca_crt
x5c = get_x5c_chain(combined)
print('x5c length:', len(x5c))

now = int(time.time())
payload = {'iss': sat['id'], 'sub': sat['id'], 'aud': sat['id'], 'jti': str(uuid.uuid4()), 'iat': now, 'exp': now+30, 'client_id': sat['id']}
header = {'x5c': x5c}
token = pyjwt.encode(payload, client_key, algorithm='RS256', headers=header)

with app.test_client() as c:
    try:
        r = c.get('/trusted_list', headers={'Authorization': 'Bearer ' + token})
        print('STATUS:', r.status_code)
        print('DATA:', r.data.decode()[:1000])
    except Exception as e:
        traceback.print_exc()
