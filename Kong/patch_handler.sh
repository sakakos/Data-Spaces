#!/bin/sh
FILE=/usr/local/share/lua/5.1/kong/plugins/ngsi-ishare-policies/handler.lua
cp $FILE ${FILE}.bak
sed -i 's|local err = ishare.handle_ngsi_request(proxy_config, req_dict)|local ok2, err = pcall(ishare.handle_ngsi_request, proxy_config, req_dict); if not ok2 then kong.log.err("PCALL_EXCEPTION: ", tostring(err)) end|' $FILE
echo "Patched. Result:"
grep -n "pcall\|handle_ngsi_request" $FILE
