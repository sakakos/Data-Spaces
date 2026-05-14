const fs = require('fs');
let content = fs.readFileSync('/usr/local/share/lua/5.1/kong/plugins/ngsi-ishare-policies/handler.lua', 'utf8');
content = content.replace(
  'local err = ishare.handle_ngsi_request(proxy_config, req_dict)',
  'local ok, err = pcall(ishare.handle_ngsi_request, proxy_config, req_dict)\n   if not ok then kong.log.err(\"PCALL EXCEPTION: \", tostring(err)) end'
);
fs.writeFileSync('/usr/local/share/lua/5.1/kong/plugins/ngsi-ishare-policies/handler.lua', content);
console.log('Done');
