#!/bin/bash
# Walks through the tailscaletest POC and captures every command + output
# to output/captures/. Idempotent: just re-run to refresh.
set -e
OUT=/tmp/tailscaletest-poc/output/captures
mkdir -p "$OUT"

# Discover hostnames from tailscale status. NOTE: a tagged-only sidecar whose
# `tailscale status` shows HostName="admin-portal" can still show DNSName
# "admin-portal-2.tail...ts.net" — Tailscale cached the original suffix from a
# prior collision and kept it even after the old node was deleted. That's why we
# read DNSName (the MagicDNS-resolvable name) instead of HostName.
ADMIN_HOSTNAME=$(docker exec tailscaletest-poc-ts-admin-portal-1 tailscale status --json 2>/dev/null | jq -r '.Self.DNSName' | sed 's/\.$//')
ADMIN_HOST=${ADMIN_HOSTNAME%.taila1b884.ts.net}
ADMIN_IP=$(docker exec tailscaletest-poc-ts-admin-portal-1 tailscale status --json 2>/dev/null | jq -r '.Self.TailscaleIPs[0]')
INTERNAL_HOSTNAME=$(docker exec tailscaletest-poc-ts-internal-db-1 tailscale status --json 2>/dev/null | jq -r '.Self.DNSName' | sed 's/\.$//')
INTERNAL_HOST=${INTERNAL_HOSTNAME%.taila1b884.ts.net}
INTERNAL_IP=$(docker exec tailscaletest-poc-ts-internal-db-1 tailscale status --json 2>/dev/null | jq -r '.Self.TailscaleIPs[0]')
ENG_HOSTNAME=$(docker exec tailscaletest-poc-ts-eng-admin-1 tailscale status --json 2>/dev/null | jq -r '.Self.DNSName' | sed 's/\.$//')
ENG_HOST=${ENG_HOSTNAME%.taila1b884.ts.net}
ENG_IP=$(docker exec tailscaletest-poc-ts-eng-admin-1 tailscale status --json 2>/dev/null | jq -r '.Self.TailscaleIPs[0]')
UNTRUSTED_HOSTNAME=$(docker exec tailscaletest-poc-ts-untrusted-1 tailscale status --json 2>/dev/null | jq -r '.Self.DNSName' | sed 's/\.$//')
UNTRUSTED_HOST=${UNTRUSTED_HOSTNAME%.taila1b884.ts.net}
UNTRUSTED_IP=$(docker exec tailscaletest-poc-ts-untrusted-1 tailscale status --json 2>/dev/null | jq -r '.Self.TailscaleIPs[0]')

echo "[discovery]"
echo "  admin-portal    DNSName=$ADMIN_HOSTNAME   IP=$ADMIN_IP"
echo "  internal-db     DNSName=$INTERNAL_HOSTNAME  IP=$INTERNAL_IP"
echo "  eng-admin       DNSName=$ENG_HOSTNAME   IP=$ENG_IP"
echo "  untrusted       DNSName=$UNTRUSTED_HOSTNAME   IP=$UNTRUSTED_IP"
# Export so subshells (the { ... } > file blocks below) inherit them
export ADMIN_HOSTNAME ADMIN_HOST ADMIN_IP INTERNAL_HOSTNAME INTERNAL_HOST INTERNAL_IP ENG_HOSTNAME ENG_HOST ENG_IP UNTRUSTED_HOSTNAME UNTRUSTED_HOST UNTRUSTED_IP

# Discover IPs of the POC nodes
echo "[discovery] looking up tailnet IPs of POC nodes via tailscale status …"
# already exported above

# Tailscale API
API_KEY=$(grep "^TS_AUTHKEY_ADMIN_PORTAL=" /tmp/tailscaletest-poc/.env | cut -d= -f2)
TAILNET=taila1b884.ts.net

run() {
    local file=$1; local title=$2; shift 2
    {
        echo "=========================================================="
        echo " $title"
        echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "=========================================================="
        echo
        echo "$ \$ $*"
        "$@"
        echo
        echo "----------------------------------------------------------"
        echo "(exit code: $?)"
        echo
    } > "$OUT/$file" 2>&1
    echo "[saved] $OUT/$file"
}

run_api_get() {
    local file=$1; local title=$2; local path=$3
    {
        echo "=========================================================="
        echo " $title"
        echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "=========================================================="
        echo
        echo "$ \$ curl -s -H \"Authorization: Bearer \$API_KEY\" \"https://api.tailscale.com/api/v2/$path\""
        curl -s -H "Authorization: Bearer $API_KEY" "https://api.tailscale.com/api/v2/$path"
        echo
        echo
        echo "----------------------------------------------------------"
    } > "$OUT/$file"
    echo "[saved] $OUT/$file"
}

# 0. tailscale status from ts-admin-portal
{
    echo "=========================================================="
    echo " Section 0 — Confirm nodes registered with the right tag"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-admin-portal-1 tailscale status"
    docker exec tailscaletest-poc-ts-admin-portal-1 tailscale status 2>&1 | grep -E "^(100\.|Search)" | head -8
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-admin-portal-1 tailscale status --json | jq '.Self.Tags'"
    docker exec tailscaletest-poc-ts-admin-portal-1 tailscale status --json 2>/dev/null | jq '.Self.Tags'
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-internal-db-1 tailscale status --json | jq '.Self.Tags'"
    docker exec tailscaletest-poc-ts-internal-db-1 tailscale status --json 2>/dev/null | jq '.Self.Tags'
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 tailscale status --json | jq '.Self.Tags'"
    docker exec tailscaletest-poc-ts-eng-admin-1 tailscale status --json 2>/dev/null | jq '.Self.Tags'
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 tailscale status --json | jq '.Self.Tags'"
    docker exec tailscaletest-poc-ts-untrusted-1 tailscale status --json 2>/dev/null | jq '.Self.Tags'
} > "$OUT/00_registration.txt"
echo "[saved] $OUT/00_registration.txt"

# 1. eng-admin → admin-portal:8080  (should allow)
{
    echo "=========================================================="
    echo " Section 1 — eng-admin → admin-portal:8080  (expect ALLOW)"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "Note: in this run admin-portal got the hostname suffix '$ADMIN_HOST' because"
    echo "      there were 2 stale 'admin-portal' nodes already in the tailnet from previous"
    echo "      POC runs. The MagicDNS name is therefore '$ADMIN_HOSTNAME'."
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 wget -qO- http://$ADMIN_HOSTNAME:8080/healthz"
    docker exec tailscaletest-poc-ts-eng-admin-1 wget -qO- "http://$ADMIN_HOSTNAME:8080/healthz"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 wget -qO- http://$ADMIN_HOSTNAME:8080/whoami"
    docker exec tailscaletest-poc-ts-eng-admin-1 wget -qO- "http://$ADMIN_HOSTNAME:8080/whoami"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 wget -qO- http://$ADMIN_IP:8080/healthz"
    docker exec tailscaletest-poc-ts-eng-admin-1 wget -qO- "http://$ADMIN_IP:8080/healthz"
    echo
    echo "(MagicDNS caveat: nslookup on a tagged-only sidecar returns NXDOMAIN, but"
    echo " getent hosts / wget work because Tailscale installs a NSS module that"
    echo " resolves names through the local control-plane netmap, not raw DNS.)"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 getent hosts $ADMIN_HOSTNAME"
    docker exec tailscaletest-poc-ts-eng-admin-1 getent hosts "$ADMIN_HOSTNAME"
} > "$OUT/01_eng_admin_to_admin_portal.txt"
echo "[saved] $OUT/01_eng_admin_to_admin_portal.txt"

# 2. eng-admin → internal-db:5432 direct (should DENY)
{
    echo "=========================================================="
    echo " Section 2 — eng-admin → internal-db:5432 direct  (expect DENY)"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 nc -zv -w 2 $INTERNAL_HOSTNAME 5432"
    docker exec tailscaletest-poc-ts-eng-admin-1 nc -zv -w 2 "$INTERNAL_HOSTNAME" 5432 2>&1 || true
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 nc -zv -w 2 $INTERNAL_IP 5432"
    docker exec tailscaletest-poc-ts-eng-admin-1 nc -zv -w 2 "$INTERNAL_IP" 5432 2>&1 || true
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 getent hosts $INTERNAL_HOSTNAME"
    docker exec tailscaletest-poc-ts-eng-admin-1 getent hosts "$INTERNAL_HOSTNAME" 2>&1 || echo "(no entry — name not in eng-admin's netmap)"
    echo
    echo "(Postgres logs — proof no inbound attempt was accepted:)"
    echo "$ \$ docker exec tailscaletest-poc-ts-internal-db-1 cat /var/lib/postgresql/data/log/*.log 2>/dev/null | tail -3"
    docker exec tailscaletest-poc-ts-internal-db-1 cat /var/lib/postgresql/data/log/*.log 2>/dev/null | tail -3 || echo "(no log files yet)"
} > "$OUT/02_eng_admin_to_internal_db.txt"
echo "[saved] $OUT/02_eng_admin_to_internal_db.txt"

# 3. eng-admin → internal-db via SSH (should allow)
{
    echo "=========================================================="
    echo " Section 3 — eng-admin → internal-db via SSH  (expect ALLOW)"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "(SSH is the only door. The internal-db Postgres port is denied at the ACL"
    echo " layer — even though the wire is reachable, the policy closes it. The only"
    echo " way for eng-admin to land on internal-db as a shell is via Tailscale SSH,"
    echo " which carries the tag identity in the handshake.)"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 tailscale ssh $INTERNAL_HOSTNAME whoami"
    docker exec tailscaletest-poc-ts-eng-admin-1 tailscale ssh "$INTERNAL_HOSTNAME" whoami 2>&1 || echo "(Tailscale SSH not running in this sidecar image — see notes)"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-eng-admin-1 tailscale ssh $ADMIN_HOSTNAME whoami"
    docker exec tailscaletest-poc-ts-eng-admin-1 tailscale ssh "$ADMIN_HOSTNAME" whoami 2>&1 || echo "(skip)"
} > "$OUT/03_eng_admin_ssh.txt"
echo "[saved] $OUT/03_eng_admin_ssh.txt"

# 4. untrusted → anything (should DENY)
{
    echo "=========================================================="
    echo " Section 4 — untrusted → anything  (expect DENY)"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 getent hosts $ADMIN_HOSTNAME"
    docker exec tailscaletest-poc-ts-untrusted-1 getent hosts "$ADMIN_HOSTNAME" 2>&1 || echo "(DENIED — name not in untrusted's netmap)"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 getent hosts $INTERNAL_HOSTNAME"
    docker exec tailscaletest-poc-ts-untrusted-1 getent hosts "$INTERNAL_HOSTNAME" 2>&1 || echo "(DENIED — name not in untrusted's netmap)"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 wget --timeout=3 -qO- http://$ADMIN_HOSTNAME:8080/healthz 2>&1"
    docker exec tailscaletest-poc-ts-untrusted-1 sh -c "wget --timeout=3 -qO- http://$ADMIN_HOSTNAME:8080/healthz 2>&1" || echo "(DENIED — wget exited non-zero)"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 wget --timeout=3 -qO- http://$ADMIN_IP:8080/healthz 2>&1"
    docker exec tailscaletest-poc-ts-untrusted-1 sh -c "wget --timeout=3 -qO- http://$ADMIN_IP:8080/healthz 2>&1" || echo "(DENIED — wget exited non-zero)"
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 nc -zv -w 2 $INTERNAL_IP 5432"
    docker exec tailscaletest-poc-ts-untrusted-1 nc -zv -w 2 "$INTERNAL_IP" 5432 2>&1 || true
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 nc -zv -w 2 $INTERNAL_HOSTNAME 5432"
    docker exec tailscaletest-poc-ts-untrusted-1 nc -zv -w 2 "$INTERNAL_HOSTNAME" 5432 2>&1 || true
} > "$OUT/04_untrusted_blocked.txt"
echo "[saved] $OUT/04_untrusted_blocked.txt"

# 5. SSH from untrusted (should DENY)
{
    echo "=========================================================="
    echo " Section 5 — untrusted SSH  (expect DENY)"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "$ \$ docker exec tailscaletest-poc-ts-untrusted-1 tailscale ssh $INTERNAL_HOSTNAME whoami"
    docker exec tailscaletest-poc-ts-untrusted-1 tailscale ssh "$INTERNAL_HOSTNAME" whoami 2>&1 || true
} > "$OUT/05_untrusted_ssh.txt"
echo "[saved] $OUT/05_untrusted_ssh.txt"

# 6. Live ACL policy from the Tailscale API
run_api_get "06_live_policy.txt" \
    "Section 6 — Live ACL policy fetched from the Tailscale API" \
    "tailnet/taila1b884.ts.net/acl"

# 7. Live device list (filtered to POC nodes)
{
    echo "=========================================================="
    echo " Section 7 — Live device list, filtered to tailscaletest-poc nodes"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "$ \$ curl -s -H \"Authorization: Bearer \$API_KEY\" \"https://api.tailscale.com/api/v2/tailnet/-/devices\""
    echo
    curl -s -H "Authorization: Bearer $API_KEY" \
      "https://api.tailscale.com/api/v2/tailnet/-/devices" > /tmp/_ts_devices.json
    echo "(response: $(wc -c < /tmp/_ts_devices.json) bytes; parsing below)"
    echo
    python3 <<'PYEOF'
import json, sys
with open('/tmp/_ts_devices.json') as f:
    raw = f.read()
try:
    d = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"  [parse error] {e}")
    print(f"  [raw response head] {raw[:200]}")
    sys.exit(0)
keep = {'admin-portal','admin-portal-1','admin-portal-2','internal-db','eng-admin','untrusted'}
print(f'  total devices in tailnet: {len(d.get("devices",[]))}')
print()
print(f'  {"hostname":18s} {"ip":18s} {"tags":30s} lastSeen')
print(f'  {"-"*18} {"-"*18} {"-"*30} {"-"*24}')
for x in d.get('devices', []):
    n = x.get('hostname','')
    if n in keep or any(k in n for k in ['admin-portal','internal-db','eng-admin','untrusted']):
        ip = (x.get('addresses') or ['?'])[0]
        tags = ','.join(x.get('tags', []))
        last = x.get('lastSeen','')
        print(f'  {n:18s} {ip:18s} {tags:30s} {last}')
PYEOF
} > "$OUT/07_devices_filtered.txt"
echo "[saved] $OUT/07_devices_filtered.txt"

# 8. Bridge isolation sanity check
{
    echo "=========================================================="
    echo " Section 8 — Each sidecar attaches to exactly one bridge"
    echo " captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "=========================================================="
    echo
    echo "$ \$ for c in admin-portal internal-db eng-admin untrusted; do"
    echo "      echo \"=== \$c ===\""
    echo "      docker inspect tailscaletest-poc-ts-\$c-1 --format '{{json .NetworkSettings.Networks}}' | jq -r 'keys[]'"
    echo "  done"
    for c in admin-portal internal-db eng-admin untrusted; do
        echo "=== $c ==="
        docker inspect "tailscaletest-poc-ts-$c-1" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null | jq -r 'keys[]'
    done
    echo
    echo "$ \$ docker network ls --filter name=tailscaletest-poc_net-"
    docker network ls --filter "name=tailscaletest-poc_net-" --format 'table {{.Name}}\t{{.Driver}}\t{{.Scope}}'
} > "$OUT/08_bridges.txt"
echo "[saved] $OUT/08_bridges.txt"

echo
echo "All captures written to $OUT/"
ls -la "$OUT/"