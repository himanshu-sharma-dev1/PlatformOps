#!/usr/bin/env bash
set -eu

PROPS=/opt/nifi/nifi-current/conf/nifi.properties

# The local MVP intentionally runs NiFi over plain HTTP on the cPlatform
# service port.  Keep these overrides at container start so a stock NiFi
# archive and the committed image behave the same way after a rebuild.
sed -i -E \
  -e '/^[[:space:]]*nifi\.web\.(http|https)\.(host|port)[[:space:]]*=/d' \
  -e '/^[[:space:]]*nifi\.security\.(keystore|truststore|user\.authorizer|user\.login\.identity\.provider|allow\.anonymous\.authentication)[[:space:]]*=/d' \
  -e '/^[[:space:]]*nifi\.remote\.input\.(secure|http\.enabled)[[:space:]]*=/d' \
  "$PROPS"

cat >> "$PROPS" <<'EOF'
nifi.web.http.host=0.0.0.0
nifi.web.http.port=8883
nifi.web.https.host=
nifi.web.https.port=
nifi.security.keystore=
nifi.security.truststore=
nifi.security.user.authorizer=
nifi.security.user.login.identity.provider=
nifi.security.allow.anonymous.authentication=true
nifi.remote.input.secure=false
nifi.remote.input.http.enabled=false
EOF

exec /opt/nifi/nifi-current/bin/nifi.sh run
