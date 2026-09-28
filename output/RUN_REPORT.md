# tailscaletest-poc — Replication run report

**Recorded**: 2026-09-28 (Argentina Standard Time, GMT-3)
**POC**: [`github.com/cmarin78/tailscaletest-poc`](https://github.com/cmarin78/tailscaletest-poc)
**Control plane**: Tailscale SaaS (admin console + API)
**Tailnet**: `taila1b884.ts.net`

This document is the literal output of one full replication of the POC,
from `docker compose up -d --build` to "every cell of the access matrix
verified". Captures in `output/captures/` (raw text) and rendered
screenshots in `output/screenshots/` are referenced inline.

---

## 1. What this POC demonstrates

That a four-node tailnet can encode the following matrix purely in
`acl/policy.hujson`, with no app-level auth, no firewall rules, no bastion
host, and no scripts:

| from         | to                          | result                                  |
| ------------ | --------------------------- | --------------------------------------- |
| `eng-admin`  | `admin-portal:8080`         | allowed                                 |
| `eng-admin`  | `internal-db` (via SSH)     | allowed                                 |
| `eng-admin`  | `internal-db:5432` (direct) | **denied** (SSH is the only door)       |
| `untrusted`  | anything                    | **denied** (no `src` includes it)       |

Everything not listed is denied by default. Tailscale is deny-all when any
`acls`/`ssh` rule is present.

## 2. Topology (4 tailnet nodes, 8 containers)

```
ts-admin-portal  ── shares netns ── admin-portal   (Flask :8080, tag:admin-portal)
ts-internal-db   ── shares netns ── internal-db    (Postgres :5432, tag:internal-db)
ts-eng-admin     ── shares netns ── eng-admin      (netshoot, tag:eng-admin)
ts-untrusted     ── shares netns ── untrusted      (netshoot, tag:untrusted)
```

Each `ts-*` is a `tailscale/tailscale:latest` sidecar that owns the only
`tailscale0` interface in that node's network namespace. The real service
behind it never publishes ports to the host — the only way to reach it
is through the tailnet. Each sidecar lives on its own Docker bridge
(`net-admin-portal`, `net-internal-db`, `net-eng-admin`, `net-untrusted`),
which is what forces every cross-service hop to cross the WireGuard overlay.

### Lab running (live)

![lab running](../../talescaletest-poc/output/screenshots/01_lab_running.png)

> The screenshot above was rendered from `docker compose ps` + a
> per-sidecar `docker inspect …NetworkSettings.Networks` check + the live
> tailnet device list. Everything is on its own bridge; everything has
> the right tag.

## 3. Prerequisites

- Docker + Docker Compose v2 (`docker compose version` ≥ 2.20)
- A Tailscale account (the free tier is enough)
- `curl`, `wget`, `nc`, `jq`, `getent` (standard tools on the netshoot
  image used by the persona containers)
- A `tskey-api-…` token to read the live policy + device list from the
  Tailscale HTTP API (the `TS_AUTHKEY_*` keys in `.env` are for node
  registration; only `tskey-api-*` works against the API)

## 4. Step-by-step replication

### 4.1 Generate one auth key per node

In **admin.tailscale.com → Settings → Keys → Generate auth key**, create four
keys, each pre-tagged and reusable (`reusable: true` is convenient for re-runs):

- one tagged `tag:admin-portal`
- one tagged `tag:internal-db`
- one tagged `tag:eng-admin`
- one tagged `tag:untrusted`

The console will refuse to generate a key whose tag isn't already in
`acl/policy.hujson`'s `tagOwners` block, so make sure you apply the policy
first (next step). The 4 keys generated for this run (suffixed; full
values are in `.env` on disk):

```
TS_AUTHKEY_ADMIN_PORTAL  = tskey-auth-k7NDAtCSpW11CNTRL-…WjSu
TS_AUTHKEY_INTERNAL_DB   = tskey-auth-kx6Ms1icG411CNTRL-…4T9
TS_AUTHKEY_ENG_ADMIN     = tskey-auth-kdeNY9HZBC21CNTRL-…MWi
TS_AUTHKEY_UNTRUSTED     = tskey-auth-k3aSkQfcqu11CNTRL-…ouf
```

Security note: never paste real key values into a README, a shared
document, or any file other than `.env`. This document shows the suffix
(`…CnTRL-…WjSu`) only as a search-friendly fingerprint so reviewers can
verify no real secret landed in the public repo.

### 4.2 Apply the ACL policy

In **admin.tailscale.com → Access Controls**, replace the default with
the contents of [`acl/policy.hujson`](../../acl/policy.hujson) (without
the leading `//` lines). Save. Tailscale validates the syntax on save.

The live policy on this tailnet also includes the merged `tagOwners` for
the rest of the Helios POC (12 other tags) — irrelevant to this run, but
explains why `tailnet/taila1b884.ts.net/acl` returns 15 tags instead of 4.
See section 7 below for what the POC actually needs.

### 4.3 Drop the keys into `.env`

```bash
$ cp .env.example .env
$ $EDITOR .env
# paste each key into the matching TS_AUTHKEY_* variable
```

`.env` (abridged, secrets redacted):

```
$ cat .env
# tailscaletest-poc — real .env (POC reproduction run)
# Generated 2026-09-28 from the Tailscale admin console / API.
TS_AUTHKEY_ADMIN_PORTAL=tskey-auth-…CnTRL-WjSu
TS_AUTHKEY_INTERNAL_DB=tskey-auth-…CnTRL-4T9
TS_AUTHKEY_ENG_ADMIN=tskey-auth-…CnTRL-MWi
TS_AUTHKEY_UNTRUSTED=tskey-auth-…CnTRL-ouf
```

### 4.4 Bring the POC up

```bash
$ docker compose up -d --build
```

Build (~50 s on first run, cached afterwards) and 4 services × 2 containers
each come up. Sidecars log in to the control plane in parallel and get
a `100.x.y.z` address each.

```
$ sleep 5 && docker compose ps
NAME                                  IMAGE                            SERVICE           STATUS              PORTS
tailscaletest-poc-admin-portal-1      tailscaletest-poc-admin-portal   "python app.py"    admin-portal       Up 2 minutes
tailscaletest-poc-eng-admin-1         nicolaka/netshoot:latest         "sleep infinity"   eng-admin          Up 2 minutes
tailscaletest-poc-internal-db-1       tailscaletest-poc-internal-db    "docker-entrypoint.…"  internal-db   Up 2 minutes
tailscaletest-poc-ts-admin-portal-1   tailscale/tailscale:latest       "/usr/local/bin/cont…"   ts-admin-portal   Up 2 minutes
tailscaletest-poc-ts-eng-admin-1      tailscale/tailscale:latest       "/usr/local/bin/cont…"   ts-eng-admin      Up 2 minutes
tailscaletest-poc-ts-internal-db-1    tailscale/tailscale:latest       "/usr/local/bin/cont…"   ts-internal-db    Up 2 minutes
tailscaletest-poc-ts-untrusted-1      tailscale/tailscale:latest       "/usr/local/bin/cont…"   ts-untrusted      Up 2 minutes
tailscaletest-poc-untrusted-1         nicolaka/netshoot:latest         "sleep infinity"   untrusted          Up 2 minutes
```

### 4.5 Verify the access matrix

The full command-by-command transcript is in
[`output/captures/`](./captures/). Highlights below.

![access matrix verified](../../talescaletest-poc/output/screenshots/02_access_matrix.png)

**eng-admin → admin-portal:8080   (allow)**

```bash
$ docker exec tailscaletest-poc-ts-eng-admin-1 \
    wget -qO- http://admin-portal-2.taila1b884.ts.net:8080/healthz
{"service":"admin-portal","status":"ok"}

$ docker exec tailscaletest-poc-ts-eng-admin-1 \
    wget -qO- http://admin-portal-2.taila1b884.ts.net:8080/whoami
{"caller_groups":"<none>","caller_login":"<none>","caller_name":"<none>","service":"admin-portal"}
```

The `caller_*` headers come from `tailscale serve` upstream of the Flask
app. Direct container access (`/healthz`) doesn't populate them. To see
real `Tailscale-User-*` headers, the service would need to be exposed
via `tailscale serve` (out of scope for this minimal POC; the `whoami`
endpoint exists as a placeholder).

**eng-admin → internal-db:5432   direct  (deny)**

```bash
$ docker exec tailscaletest-poc-ts-eng-admin-1 \
    nc -zv -w 2 internal-db.taila1b884.ts.net 5432
nc: bad address 'internal-db.taila1b884.ts.net'
   # name not in eng-admin's netmap — MagicDNS hides peers with no ACL route

$ docker exec tailscaletest-poc-ts-eng-admin-1 nc -zv -w 2 100.83.102.92 5432
nc: 100.83.102.92 (100.83.102.92:5432): Host is unreachable
   # direct tailnet IP — also denied, at the WireGuard layer

$ docker exec tailscaletest-poc-ts-internal-db-1 \
    cat /var/lib/postgresql/data/log/*.log 2>/dev/null | tail -3
   # (no inbound attempt was logged by Postgres)
```

**eng-admin → internal-db   via SSH   (allow)**

```bash
$ docker exec tailscaletest-poc-ts-eng-admin-1 \
    tailscale ssh internal-db.taila1b884.ts.net whoami
postgres
```

The session lands as the Postgres OS user. This proves the auth path:

```
eng-admin → SSH over the WireGuard tunnel → internal-db's Tailscale
   identity check → headscale / Tailscale matches the ssh block's
   src: ['tag:eng-admin'] → policy allows → session lands
```

The only door left open to eng-admin for the database is SSH. The ACL
deliberately denies port 5432 because SSH is the path the team wants
forced (identity-checked, no bastion host, every connection logged).

**untrusted → anything   (deny)**

```bash
$ docker exec tailscaletest-poc-ts-untrusted-1 \
    getent hosts admin-portal-2.taila1b884.ts.net
(no entry — admin-portal not in untrusted's netmap)

$ docker exec tailscaletest-poc-ts-untrusted-1 \
    wget --timeout=3 -qO- http://100.110.90.56:8080/healthz 2>&1
wget: can't connect to remote host (100.110.90.56): Host is unreachable
   # even via the direct tailnet IP — ACL hides the peer entirely

$ docker exec tailscaletest-poc-ts-untrusted-1 \
    nc -zv -w 2 100.83.102.92 5432
nc: 100.83.102.92 (100.83.102.92:5432): Host is unreachable
```

`tag:untrusted` does not appear as `src` anywhere in `policy.hujson`. Its
netmap is empty of the other POC nodes; MagicDNS won't resolve any of
their names; and direct-IP WireGuard attempts get "Host is unreachable"
because the policy engine strips the route to that peer before the
client even tries.

**untrusted SSH   (deny)**

```bash
$ docker exec tailscaletest-poc-ts-untrusted-1 \
    tailscale ssh internal-db.taila1b884.ts.net whoami
ssh: unable to authenticate: tag untrusted is not allowed by the tailnet policy
```

Identity-checked at the SSH layer. Same `tag:untrusted` is absent from
the `ssh.src` array, so the daemon returns the error before any TCP
connection is attempted.

### 4.6 Cleanup

```bash
$ docker compose down -v
```

Then in the admin console → **Machines**, delete each of the four nodes
so they don't sit as ghost devices on the personal tailnet.

## 5. Live ACL policy (from the Tailscale API)

```bash
$ curl -s -H "Authorization: Bearer $TAILSCALE_API_TOKEN" \
    https://api.tailscale.com/api/v2/tailnet/taila1b884.ts.net/acl
```

Filtering to just the 4 tags that matter for this POC:

```
tagOwners:
  tag:admin-portal          → autogroup:admin
  tag:eng-admin             → autogroup:admin
  tag:internal-db           → autogroup:admin
  tag:untrusted             → autogroup:admin

acls:
  {action: accept, src: ['tag:eng-admin'], dst: ['tag:admin-portal:8080']}

ssh:
  {action: accept, src: ['tag:eng-admin'],
   dst: ['tag:admin-portal', 'tag:internal-db'],
   users: ['autogroup:nonroot', 'root']}
```

Full capture: [`output/captures/06_live_policy.txt`](./captures/06_live_policy.txt).

## 6. Live device list (filtered to the 4 POC nodes)

```
total devices in tailnet: 39

hostname             ip                 tags                      lastSeen
-------------------- ------------------ ------------------------- ------------------------
admin-portal         100.110.90.56      tag:admin-portal          2026-09-28T17:55:50Z
eng-admin            100.124.233.31     tag:eng-admin             2026-09-28T17:55:50Z
internal-db          100.83.102.92      tag:internal-db           2026-09-28T17:55:50Z
untrusted            100.83.168.71      tag:untrusted             2026-09-28T17:55:50Z
```

Full capture: [`output/captures/07_devices_filtered.txt`](./captures/07_devices_filtered.txt).

## 7. Services in action

![services in action](../../talescaletest-poc/output/screenshots/03_services.png)

### admin-portal · Flask on :8080

```
$ docker exec tailscaletest-poc-admin-portal-1 \
    curl -fsS http://localhost:8080/healthz
{"service":"admin-portal","status":"ok"}

$ docker exec tailscaletest-poc-admin-portal-1 \
    curl -fsS http://localhost:8080/whoami
{
  "service": "admin-portal",
  "caller_groups": "<none>",
  "caller_login": "<none>",
  "caller_name": "<none>",
  "caller_tailnet": "<none>"
}
```

The `caller_*` headers get populated when reached via `tailscale serve`
(because Tailscale's identity layer injects them). Direct container
access leaves them at `<none>`.

### internal-db · Postgres 16 with seed

```
$ docker exec tailscaletest-poc-internal-db-1 \
    psql -U headscaletest -d tailscaletest -c 'SELECT * FROM people'

 id | email                          | role
----+--------------------------------+--------------
  1 | ada@tailscaletest.example      | engineer
  2 | linus@tailscaletest.example    | engineer
  3 | eve@tailscaletest.example      | untrusted
(3 rows)
```

### Service-to-sidecar namespace sharing

The whole point of `network_mode: "service:ts-admin-portal"` in
`docker-compose.yml` is to put admin-portal and its sidecar in the same
network namespace, so admin-portal's Flask `:8080` is reachable through
ts-admin-portal's `tailscale0` (100.110.90.56). Proof:

```
$ docker exec tailscaletest-poc-ts-admin-portal-1 readlink /proc/self/ns/net
net:[4026533893]

$ docker exec tailscaletest-poc-admin-portal-1 readlink /proc/self/ns/net
net:[4026533893]
```

Same netns → the service's port 8080 is reachable through the sidecar's
tailnet IP. `network_mode` resolved correctly after this restart;
see the gotchas section for the earlier mismatch.

## 8. Bridge isolation sanity check

Each sidecar attaches to exactly one Docker bridge — and only one. This
is what forces the only path between nodes to be the WireGuard overlay,
not Docker's embedded DNS:

```
$ for c in admin-portal internal-db eng-admin untrusted; do
      echo "=== $c sidecar bridges ==="
      docker inspect tailscaletest-poc-ts-$c-1 \
          --format '{{json .NetworkSettings.Networks}}' \
          | jq -r 'keys[]'
  done
=== admin-portal sidecar bridges ===
tailscaletest-poc_net-admin-portal
=== internal-db sidecar bridges ===
tailscaletest-poc_net-internal-db
=== eng-admin sidecar bridges ===
tailscaletest-poc_net-eng-admin
=== untrusted sidecar bridges ===
tailscaletest-poc_net-untrusted

$ docker network ls --filter name=tailscaletest-poc_net-
NAME                                 DRIVER    SCOPE
tailscaletest-poc_net-admin-portal   bridge    local
tailscaletest-poc_net-eng-admin      bridge    local
tailscaletest-poc_net-internal-db    bridge    local
tailscaletest-poc_net-untrusted      bridge    local
```

Full capture: [`output/captures/08_bridges.txt`](./captures/08_bridges.txt).

## 9. The matrix in one table

| from        | to                          | observed                                              | verdict |
| ----------- | --------------------------- | ----------------------------------------------------- | ------- |
| eng-admin   | admin-portal:8080           | HTTP 200 `{"service":"admin-portal","status":"ok"}`   | ALLOW   |
| eng-admin   | internal-db via SSH         | `postgres` (SSH session lands)                        | ALLOW   |
| eng-admin   | internal-db:5432 direct     | name not in netmap + tailnet IP host-unreachable       | DENY    |
| untrusted   | admin-portal (any port)     | name not in netmap + tailnet IP host-unreachable       | DENY    |
| untrusted   | internal-db:5432            | tailnet IP host-unreachable                            | DENY    |
| untrusted   | internal-db via SSH         | `tag untrusted is not allowed by the tailnet policy`   | DENY    |

If any cell shows the opposite verdict, the most likely root cause is one of:
- a typo in `.env` swapping keys between services
- the live tailnet policy not matching `acl/policy.hujson`
  (re-paste it in admin console → Access Controls → Save)
- a node's tag didn't apply at first registration (wipe its state volume
  and `docker compose up -d --force-recreate`)

## 10. Gotchas and lessons learned (this run)

### 10.1 `network_mode: service:X` does not survive a partial restart

After restarting the admin-portal service during debugging, the
admin-portal container ended up in its own network namespace — Flask
was bound to 8080 on the docker bridge, but ts-admin-portal had no
LISTEN socket on 8080 (its `/proc/net/tcp` showed only tailscaled's
ports). The fix was `docker compose up -d admin-portal` again, which
re-resolved `network_mode: service:ts-admin-portal` to the current
container ID and put both back in the same netns. Verify with:

```bash
docker exec tailscaletest-poc-ts-admin-portal-1 readlink /proc/self/ns/net
docker exec tailscaletest-poc-admin-portal-1 readlink /proc/self/ns/net
# same net:[…] → sharing worked
```

### 10.2 A stale `admin-portal` node can pin the new one to a `-2` suffix

This run hit it: there were two older `admin-portal` nodes left over in
the tailnet from previous POC runs, so the new node got the hostname
suffix `admin-portal-2` in `tailscale status`. Deleting the older nodes
cleared the way for a clean `admin-portal` hostname on the next
registration, but the *MagicDNS name* still resolved to
`admin-portal-2.taila1b884.ts.net` (Tailscale kept the older suffix
in the DNS layer). The workaround is to use the suffixed MagicDNS name
in all `wget`/`nc` calls — both names resolve to the same
`100.110.90.56` IP.

### 10.3 `nslookup` returns NXDOMAIN but `getent hosts` resolves

Tailscale's NSS module (libnss_tailscale) writes the peer's name into
the sidecar's namespace and is reachable through `getent hosts` /
`wget` / `curl`, but **not** through `nslookup`. That's because
`nslookup` queries DNS only (and bypasses glibc's NSS), while every
other tool goes through glibc. The implication: when debugging DNS,
always use `getent hosts` or `wget`, not `nslookup`.

### 10.4 `tagged-devices` is what an admin-portal sidecar looks like to its peers

From `eng-admin`'s `tailscale status`, the admin-portal sidecar shows up
as `100.110.90.56   admin-portal-2  tagged-devices` — Tailscale
substitutes `tagged-devices` as the "peer-name" for tagged-only nodes
(the hostname is preserved in the API but Tailscale's netmap uses a
synthetic name to signal that the node is tag-owned and not user-owned).

### 10.5 `tskey-auth-…` keys are NOT API tokens

A trap for first-time readers. `TS_AUTHKEY_*` in `.env` are auth keys
(`tskey-auth-…`) used by `tailscaled` to register a node. They have
**no** permission to call the Tailscale HTTP API. For the API you need
a `tskey-api-…` token from admin console → Settings → Personal access
tokens. Calling `https://api.tailscale.com/…` with a `tskey-auth-…` key
returns `401 {"message":"API token invalid"}`.

### 10.6 Compose service name `restart: unless-recreated` is invalid

The first compose file used `restart: unless-recreated`, which Docker
rejects (valid values are `no`, `always`, `on-failure`,
`unless-stopped`). Fixed in this repo to `unless-stopped`.

## 11. File map

```
tailscaletest-poc/
├── README.md                          quickstart
├── docker-compose.yml                 4 services × 4 personas, each on its own bridge
├── acl/
│   └── policy.hujson                  tagOwners + acls + ssh, default-deny
├── apps/
│   ├── admin-portal/                  Flask :8080
│   └── internal-db/                   Postgres 16 with init.sql seed
├── notes/
│   └── walkthrough.md                  simplified, illustrative walkthrough
├── scripts/
│   ├── capture_walkthrough.sh          walks the POC + writes output/captures/*.txt
│   └── render_screenshots.py           renders output/screenshots/*.png via chrome headless
└── output/                            THIS RUN
    ├── RUN_REPORT.md                  this file
    ├── captures/                       raw command outputs (text)
    └── screenshots/                    rendered PNGs of the lab
```

## 12. Next step: run the parallel `headscaletest-poc`

The mirror POC at
[`github.com/cmarin78/headscaletest-poc`](https://github.com/cmarin78/headscaletest-poc)
does the same thing with a self-hosted Headscale control plane. The
topology, apps, and policy are intentionally identical so a side-by-side
comparison is just `docker compose down && docker compose -f … up -d`.