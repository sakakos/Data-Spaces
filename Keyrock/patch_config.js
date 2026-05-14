const fs = require('fs');
let content = fs.readFileSync('/opt/fiware-idm/lib/configService.js', 'utf8');
content = content.replace(
  'config.pr.client_key = process.env.IDM_PR_CLIENT_KEY;',
  'config.pr.client_key = process.env.IDM_PR_CLIENT_KEY.startsWith("/") ? fs.readFileSync(process.env.IDM_PR_CLIENT_KEY, "utf8") : process.env.IDM_PR_CLIENT_KEY;'
);
content = content.replace(
  'config.pr.client_crt = process.env.IDM_PR_CLIENT_CRT;',
  'config.pr.client_crt = process.env.IDM_PR_CLIENT_CRT.startsWith("/") ? fs.readFileSync(process.env.IDM_PR_CLIENT_CRT, "utf8") : process.env.IDM_PR_CLIENT_CRT;'
);
fs.writeFileSync('/opt/fiware-idm/lib/configService.js', content);
console.log('Done');
