# tailscaletest-poc

Minimal, experimental POC: **tag-based ACLs with the Tailscale SaaS control plane**.

No scripts. No `heliosctl`. No `verify.sh`. Just `docker compose`, `curl`, `tailscale status`,
and the actual outputs from running them. The point of this repo is to be small enough to
read top-to-bottom in one sitting, and reproducible by hand in under 30 minutes.

This is the **Tailscale SaaS** half of a two-repo comparison. The parallel
**Headscale self-hosted** variant lives in
[`cmarin78/headscaletest-poc`](https://github.com/cmarin78/headscaletest-poc).

## What this POC demonstrates

That a four-node tailnet can encode the following matrix purely in
`acl/policy.hujson`, with no app-level auth, no firewall rules, no bastion host:

| from         | to                          | result                                  |
| ------------ | --------------------------- | --------------------------------------- |
| `eng-admin`  | `admin-portal:8080`         | allowed                                 |
| `eng-admin`  | `internal-db` (via SSH)     | allowed                                 |
| `eng-admin`  | `internal-db:5432` (direct) | **denied** (SSH is the only door)       |
| `untrusted`  | anything                    | **denied** (no `src` includes it)       |

Everything not listed is denied by default. Tailscale is deny-all when any
`acls`/`ssh` rule is present.

## Topology (4 nodes)

```
ts-admin-portal  ── shares netns with ── admin-portal   (Flask :8080, tag:admin-portal)
ts-internal-db   ── shares netns with ── internal-db    (Postgres :5432, tag:internal-db)
ts-eng-admin     ── shares netns with ── eng-admin      (netshoot, tag:eng-admin)
ts-untrusted     ── shares netns with ── untrusted      (netshoot, tag:untrusted)
```

Each `ts-*` is a `tailscale/tailscale:latest` sidecar that owns the only `tailscale0`
interface in that node's network namespace. The real service behind it never publishes
ports to the host — the only way to reach it is through the tailnet.

Each sidecar lives on its own Docker bridge. That is the whole point: it forces
service-to-service traffic to cross the real tailnet (not Compose's embedded DNS),
or not happen at all. See `notes/walkthrough.md` section "Why one bridge per node".

## Prerequisites

- Docker + Docker Compose v2 (`docker compose version` ≥ 2.20)
- A Tailscale account. The free tier is enough.
- `curl`, `jq` (only for sanity-checking the walkthrough)

## Replication, step by step

Each step is one or two commands. Paste them into a terminal.

### 1. Generate one auth key per node

In **admin.tailscale.com → Settings → Keys → Generate auth key**, create four keys,
each pre-tagged and reusable (re-usable is convenient for re-runs):

- one tagged `tag:admin-portal`
- one tagged `tag:internal-db`
- one tagged `tag:eng-admin`
- one tagged `tag:untrusted`

If a tag does not exist yet, the console prompts you to create it right there.
The console will refuse to let you generate a key whose tag isn't already in
`acl/policy.hujson`'s `tagOwners` block — so make sure `acl/policy.hujson` has
been pasted into **Access Controls** and saved first (step 2).

### 2. Apply the ACL policy

In **admin.tailscale.com → Access Controls**, replace the default with the
contents of [`acl/policy.hujson`](acl/policy.hujson) (without the leading `//` lines).
Save. Tailscale validates the syntax on save.

### 3. Drop the keys into `.env`

```bash
$ cp .env.example .env
$ $EDITOR .env
# paste each key into the matching TS_AUTHKEY_* variable
```

### 4. Bring the POC up

```bash
$ docker compose up -d --build
```

The first build takes ~30 seconds. Sidecars log in to the control plane in
parallel and get a `100.x.y.z` address each. Wait until `docker compose ps`
shows every container `Up`:

```bash
$ sleep 5 && docker compose ps
NAME                SERVICE             STATUS              PORTS
ts-admin-portal-1   ts-admin-portal     Up 10 seconds
admin-portal-1      admin-portal        Up 10 seconds
ts-internal-db-1    ts-internal-db      Up 10 seconds
internal-db-1       internal-db         Up 10 seconds
ts-eng-admin-1      ts-eng-admin        Up 10 seconds
eng-admin-1         eng-admin           Up 10 seconds
ts-untrusted-1      ts-untrusted        Up 10 seconds
untrusted-1         untrusted           Up 10 seconds
```

### 5. Walk through the access matrix

See [`notes/walkthrough.md`](notes/walkthrough.md) for the exact command-by-command
verification: every cell of the access matrix above, run as raw `docker exec … curl`
and `tailscale status`, with the actual outputs. The summary at the end is
one paragraph; the inputs are copy-paste runnable.

### 6. Cleanup

```bash
$ docker compose down -v
```

Then in the admin console → **Machines**, delete each of the four nodes so they
don't sit as ghost devices on your personal tailnet.

## File map

```
.
├── README.md                    this file
├── .gitignore
├── .env.example                 template — copy to .env and paste real keys
├── docker-compose.yml           4 services × 4 personas, each on its own bridge
├── acl/
│   └── policy.hujson            tagOwners + acls + ssh, default-deny
└── apps/
    ├── admin-portal/            Flask :8080, two routes (/healthz, /whoami)
    └── internal-db/             Postgres 16 with init.sql seed
```

## Repository policy

- No real keys, tokens, or `tskey-…` values are ever committed. The `.env.example`
  template is the only place those literals appear, and they are placeholders.
- The walkthrough's outputs are illustrative: they match what the POC produces
  on a clean run, but they are not extracted from a single canonical run.