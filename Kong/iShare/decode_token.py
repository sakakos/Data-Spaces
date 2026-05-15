import jwt, json, sys
token = sys.argv[1]
payload = jwt.decode(token, options={"verify_signature": False})
print(json.dumps(payload, indent=2))
