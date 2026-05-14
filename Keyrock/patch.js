const fs = require('fs');
let content = fs.readFileSync('/opt/fiware-idm/models/model_oauth_server.js', 'utf8');
content = content.replace(
  "attributes: ['id', 'username', 'email', 'description', 'website', 'gravatar', 'image', 'extra', 'eidas_id']",
  "attributes: ['id', 'username', 'email', 'description', 'website', 'gravatar', 'image', 'extra', 'eidas_id', 'admin']"
);
fs.writeFileSync('/opt/fiware-idm/models/model_oauth_server.js', content);
console.log('Done');
