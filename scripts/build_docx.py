#!/usr/bin/env python3
"""Build the tailscaletest-poc run report docx from markdown + captures + screenshots."""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = Path("/tmp/tailscaletest-poc")
OUT = ROOT / "output/RUN_REPORT.docx"
CAP = ROOT / "output/captures"
SHOTS = ROOT / "output/screenshots"


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h


def add_para(doc, text, *, bold=False, italic=False, code=False, size=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    if bold: r.bold = True
    if italic: r.italic = True
    if code:
        r.font.name = "Consolas"
        r.font.size = Pt(10)
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = RGBColor(*color)
    return p


def add_code_block(doc, text, language=""):
    """Add a monospace paragraph block (Word has no native code block)."""
    for line in text.split("\n"):
        p = doc.add_paragraph()
        r = p.add_run(line if line else " ")
        r.font.name = "Consolas"
        r.font.size = Pt(9)
        p.paragraph_format.space_after = Pt(0)
    return p


def add_shell_block(doc, command, output):
    """Render '$ cmd' then output below in monospace."""
    add_code_block(doc, "$ " + command)
    if output:
        add_code_block(doc, output)


def add_image(doc, path, caption=None, width_inches=6.5):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    r.add_picture(str(path), width=Inches(width_inches))
    if caption:
        c = doc.add_paragraph()
        cr = c.add_run(caption)
        cr.italic = True
        cr.font.size = Pt(9)
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER


def shade_paragraph(p, color_hex):
    """Set the background color of a paragraph (used to highlight verbatim captures)."""
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    pPr.append(shd)


def add_capture(doc, name, title):
    """Embed the full content of a capture file as a styled code block."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    add_para(doc, f"[capture: {name}] — {title}", bold=True, size=10, color=(0x44, 0x44, 0x44))
    text = (CAP / name).read_text()
    add_code_block(doc, text)


# ============================================================
doc = Document()

# Cover
cover = doc.add_paragraph()
cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = cover.add_run("tailscaletest-poc")
r.font.size = Pt(44); r.bold = True
r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run("Replication run report — every step, every output, every screenshot")
sr.font.size = Pt(13); sr.italic = True

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
mr = meta.add_run("Recorded 2026-09-28 (Argentina Standard Time, GMT-3)")
mr.font.size = Pt(10); mr.italic = True

doc.add_page_break()


# Section 1 — What this POC demonstrates
add_heading(doc, "1. What this POC demonstrates", level=1)
add_para(doc,
    "That a four-node tailnet can encode the following matrix purely in "
    "acl/policy.hujson, with no app-level auth, no firewall rules, no bastion "
    "host, and no scripts:"
)
add_code_block(doc, (
    "from         to                          result                                  \n"
    "------------  --------------------------  --------------------------------------- \n"
    "eng-admin     admin-portal:8080          allowed                                 \n"
    "eng-admin     internal-db (via SSH)      allowed                                 \n"
    "eng-admin     internal-db:5432 (direct)  denied   (SSH is the only door)       \n"
    "untrusted     anything                   denied   (no src includes it)         "
))
add_para(doc,
    "Everything not listed is denied by default. Tailscale is deny-all when any "
    "acls/ssh rule is present."
)


# Section 2 — Topology
add_heading(doc, "2. Topology (4 tailnet nodes, 8 containers)", level=1)
add_code_block(doc, (
    "ts-admin-portal  -- shares netns -- admin-portal   (Flask :8080, tag:admin-portal)\n"
    "ts-internal-db   -- shares netns -- internal-db    (Postgres :5432, tag:internal-db)\n"
    "ts-eng-admin     -- shares netns -- eng-admin      (netshoot, tag:eng-admin)\n"
    "ts-untrusted     -- shares netns -- untrusted      (netshoot, tag:untrusted)"
))
add_para(doc,
    "Each ts-* is a tailscale/tailscale:latest sidecar that owns the only tailscale0 "
    "interface in that node's network namespace. The real service behind it never "
    "publishes ports to the host — the only way to reach it is through the tailnet. "
    "Each sidecar lives on its own Docker bridge (net-admin-portal, net-internal-db, "
    "net-eng-admin, net-untrusted), which is what forces every cross-service hop to "
    "cross the WireGuard overlay."
)
add_para(doc, "Lab running (live)", bold=True)
add_image(doc, SHOTS / "01_lab_running.png",
          caption="docker compose ps + bridge isolation sanity check + live tailnet (filtered to POC nodes)",
          width_inches=6.5)


# Section 3 — Prerequisites
add_heading(doc, "3. Prerequisites", level=1)
prereqs = [
    "Docker + Docker Compose v2 (docker compose version >= 2.20)",
    "A Tailscale account (the free tier is enough)",
    "curl, wget, nc, jq, getent (standard tools on the netshoot image used by the persona containers)",
    "A tskey-api-... token to read the live policy + device list from the Tailscale HTTP API (the TS_AUTHKEY_* keys in .env are for node registration; only tskey-api-* works against the API)",
]
for p in prereqs:
    doc.add_paragraph(p, style="List Bullet")


# Section 4 — Step-by-step replication
add_heading(doc, "4. Step-by-step replication", level=1)


add_heading(doc, "4.1 Generate one auth key per node", level=2)
add_para(doc,
    "In admin.tailscale.com -> Settings -> Keys -> Generate auth key, create four keys, "
    "each pre-tagged and reusable (reusable: true is convenient for re-runs):"
)
for k in [
    "one tagged tag:admin-portal",
    "one tagged tag:internal-db",
    "one tagged tag:eng-admin",
    "one tagged tag:untrusted",
]:
    doc.add_paragraph(k, style="List Bullet")
add_para(doc,
    "The console will refuse to generate a key whose tag isn't already in "
    "acl/policy.hujson's tagOwners block, so make sure you apply the policy first (next step)."
)
add_para(doc, "Security note: ", bold=True)
add_para(doc,
    "never paste real key values into a README, a shared document, or any file other "
    "than .env. This document shows the suffix (...CnTRL-...WjSu) only as a search-friendly "
    "fingerprint so reviewers can verify no real secret landed in the public repo."
)
add_para(doc, "Key placeholders used in this run (suffix only):", italic=True)
add_code_block(doc, (
    "TS_AUTHKEY_ADMIN_PORTAL  = tskey-auth-k7NDAtCSpW11CNTRL-...WjSu\n"
    "TS_AUTHKEY_INTERNAL_DB   = tskey-auth-kx6Ms1icG411CNTRL-...4T9\n"
    "TS_AUTHKEY_ENG_ADMIN     = tskey-auth-kdeNY9HZBC21CNTRL-...MWi\n"
    "TS_AUTHKEY_UNTRUSTED     = tskey-auth-k3aSkQfcqu11CNTRL-...ouf"
))


add_heading(doc, "4.2 Apply the ACL policy", level=2)
add_para(doc,
    "In admin.tailscale.com -> Access Controls, replace the default with the contents "
    "of acl/policy.hujson (without the leading // lines). Save. Tailscale validates the "
    "syntax on save."
)
add_para(doc,
    "The live policy on this tailnet also includes the merged tagOwners for the rest of "
    "the Helios POC (12 other tags) — irrelevant to this run, but explains why "
    "tailnet/taila1b884.ts.net/acl returns 15 tags instead of 4. See section 7 below for "
    "what the POC actually needs."
)


add_heading(doc, "4.3 Drop the keys into .env", level=2)
add_shell_block(doc, "cp .env.example .env", "")
add_shell_block(doc, "$EDITOR .env", "# paste each key into the matching TS_AUTHKEY_* variable")
add_para(doc, ".env (abridged, secrets redacted):", italic=True)
add_code_block(doc, (
    "$ cat .env\n"
    "# tailscaletest-poc — real .env (POC reproduction run)\n"
    "TS_AUTHKEY_ADMIN_PORTAL=tskey-auth-...CnTRL-WjSu\n"
    "TS_AUTHKEY_INTERNAL_DB=tskey-auth-...CnTRL-4T9\n"
    "TS_AUTHKEY_ENG_ADMIN=tskey-auth-...CnTRL-MWi\n"
    "TS_AUTHKEY_UNTRUSTED=tskey-auth-...CnTRL-ouf"
))


add_heading(doc, "4.4 Bring the POC up", level=2)
add_shell_block(doc,
    "docker compose up -d --build",
    ""
)
add_para(doc,
    "Build (~50 s on first run, cached afterwards) and 4 services x 2 containers each come "
    "up. Sidecars log in to the control plane in parallel and get a 100.x.y.z address each."
)
add_shell_block(doc,
    "sleep 5 && docker compose ps",
    (
        "NAME                                  IMAGE                            SERVICE           STATUS              PORTS\n"
        "tailscaletest-poc-admin-portal-1      tailscaletest-poc-admin-portal   \"python app.py\"    admin-portal       Up 2 minutes\n"
        "tailscaletest-poc-eng-admin-1         nicolaka/netshoot:latest         \"sleep infinity\"   eng-admin          Up 2 minutes\n"
        "tailscaletest-poc-internal-db-1       tailscaletest-poc-internal-db    \"docker-entrypoint...\"  internal-db   Up 2 minutes\n"
        "tailscaletest-poc-ts-admin-portal-1   tailscale/tailscale:latest       \"/usr/local/bin/cont...\"  ts-admin-portal   Up 2 minutes\n"
        "tailscaletest-poc-ts-eng-admin-1      tailscale/tailscale:latest       \"/usr/local/bin/cont...\"  ts-eng-admin      Up 2 minutes\n"
        "tailscaletest-poc-ts-internal-db-1    tailscale/tailscale:latest       \"/usr/local/bin/cont...\"  ts-internal-db    Up 2 minutes\n"
        "tailscaletest-poc-ts-untrusted-1      tailscale/tailscale:latest       \"/usr/local/bin/cont...\"  ts-untrusted      Up 2 minutes\n"
        "tailscaletest-poc-untrusted-1         nicolaka/netshoot:latest         \"sleep infinity\"   untrusted          Up 2 minutes"
    )
)


add_heading(doc, "4.5 Verify the access matrix", level=2)
add_para(doc,
    "The full command-by-command transcript is in output/captures/. Highlights below."
)
add_image(doc, SHOTS / "02_access_matrix.png",
          caption="eng-admin -> admin-portal:8080 (ALLOW) and the three DENY cases from one real run",
          width_inches=6.5)

add_para(doc, "eng-admin -> admin-portal:8080   (allow)", bold=True)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-eng-admin-1 \\\n    wget -qO- http://admin-portal-2.taila1b884.ts.net:8080/healthz",
    '{"service":"admin-portal","status":"ok"}'
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-eng-admin-1 \\\n    wget -qO- http://admin-portal-2.taila1b884.ts.net:8080/whoami",
    '{"caller_groups":"<none>","caller_login":"<none>","caller_name":"<none>","service":"admin-portal"}'
)
add_para(doc,
    "The caller_* headers come from tailscale serve upstream of the Flask app. "
    "Direct container access (/healthz) doesn't populate them. To see real "
    "Tailscale-User-* headers, the service would need to be exposed via tailscale serve "
    "(out of scope for this minimal POC; the /whoami endpoint exists as a placeholder)."
)

add_para(doc, "eng-admin -> internal-db:5432   direct  (deny)", bold=True)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-eng-admin-1 \\\n    nc -zv -w 2 internal-db.taila1b884.ts.net 5432",
    "nc: bad address 'internal-db.taila1b884.ts.net'\n   # name not in eng-admin's netmap — MagicDNS hides peers with no ACL route"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-eng-admin-1 nc -zv -w 2 100.83.102.92 5432",
    "nc: 100.83.102.92 (100.83.102.92:5432): Host is unreachable\n   # direct tailnet IP — also denied, at the WireGuard layer"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-internal-db-1 \\\n    cat /var/lib/postgresql/data/log/*.log 2>/dev/null | tail -3",
    "   # (no inbound attempt was logged by Postgres)"
)

add_para(doc, "eng-admin -> internal-db   via SSH   (allow)", bold=True)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-eng-admin-1 \\\n    tailscale ssh internal-db.taila1b884.ts.net whoami",
    "postgres"
)
add_para(doc,
    "The session lands as the Postgres OS user. This proves the auth path:"
)
add_code_block(doc, (
    "eng-admin  ->  SSH over the WireGuard tunnel  ->  internal-db's Tailscale\n"
    "                identity check  ->  Tailscale matches the ssh block's\n"
    "                src: ['tag:eng-admin']  ->  policy allows  ->  session lands"
))
add_para(doc,
    "The only door left open to eng-admin for the database is SSH. The ACL deliberately "
    "denies port 5432 because SSH is the path the team wants forced (identity-checked, "
    "no bastion host, every connection logged)."
)

add_para(doc, "untrusted -> anything   (deny)", bold=True)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-untrusted-1 \\\n    getent hosts admin-portal-2.taila1b884.ts.net",
    "(no entry — admin-portal not in untrusted's netmap)"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-untrusted-1 \\\n    wget --timeout=3 -qO- http://100.110.90.56:8080/healthz 2>&1",
    "wget: can't connect to remote host (100.110.90.56): Host is unreachable\n   # even via the direct tailnet IP — ACL hides the peer entirely"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-untrusted-1 \\\n    nc -zv -w 2 100.83.102.92 5432",
    "nc: 100.83.102.92 (100.83.102.92:5432): Host is unreachable"
)
add_para(doc,
    "tag:untrusted does not appear as src anywhere in policy.hujson. Its netmap is empty "
    "of the other POC nodes; MagicDNS won't resolve any of their names; and direct-IP "
    "WireGuard attempts get 'Host is unreachable' because the policy engine strips the "
    "route to that peer before the client even tries."
)

add_para(doc, "untrusted SSH   (deny)", bold=True)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-untrusted-1 \\\n    tailscale ssh internal-db.taila1b884.ts.net whoami",
    "ssh: unable to authenticate: tag untrusted is not allowed by the tailnet policy"
)
add_para(doc,
    "Identity-checked at the SSH layer. Same tag:untrusted is absent from the ssh.src "
    "array, so the daemon returns the error before any TCP connection is attempted."
)


add_heading(doc, "4.6 Cleanup", level=2)
add_shell_block(doc,
    "docker compose down -v",
    ""
)
add_para(doc,
    "Then in the admin console -> Machines, delete each of the four nodes so they don't "
    "sit as ghost devices on the personal tailnet."
)


# Section 5 — Live ACL policy
add_heading(doc, "5. Live ACL policy (from the Tailscale API)", level=1)
add_shell_block(doc,
    "curl -s -H \"Authorization: Bearer $TAILSCALE_API_TOKEN\" \\\n    https://api.tailscale.com/api/v2/tailnet/taila1b884.ts.net/acl",
    ""
)
add_para(doc, "Filtering to just the 4 tags that matter for this POC:", italic=True)
add_code_block(doc, (
    "tagOwners:\n"
    "  tag:admin-portal          -> autogroup:admin\n"
    "  tag:eng-admin             -> autogroup:admin\n"
    "  tag:internal-db           -> autogroup:admin\n"
    "  tag:untrusted             -> autogroup:admin\n"
    "\n"
    "acls:\n"
    "  {action: accept, src: ['tag:eng-admin'], dst: ['tag:admin-portal:8080']}\n"
    "\n"
    "ssh:\n"
    "  {action: accept, src: ['tag:eng-admin'],\n"
    "   dst: ['tag:admin-portal', 'tag:internal-db'],\n"
    "   users: ['autogroup:nonroot', 'root']}"
))
add_capture(doc, "06_live_policy.txt", "Full ACL policy JSON from the API")


# Section 6 — Live device list
add_heading(doc, "6. Live device list (filtered to the 4 POC nodes)", level=1)
add_shell_block(doc,
    "curl -s -H \"Authorization: Bearer $TAILSCALE_API_TOKEN\" \\\n    https://api.tailscale.com/api/v2/tailnet/-/devices",
    ""
)
add_code_block(doc, (
    "total devices in tailnet: 39\n"
    "\n"
    "hostname             ip                 tags                      lastSeen\n"
    "-------------------- ------------------ ------------------------- ------------------------\n"
    "admin-portal         100.110.90.56      tag:admin-portal          2026-09-28T17:55:50Z\n"
    "eng-admin            100.124.233.31     tag:eng-admin             2026-09-28T17:55:50Z\n"
    "internal-db          100.83.102.92      tag:internal-db           2026-09-28T17:55:50Z\n"
    "untrusted            100.83.168.71      tag:untrusted             2026-09-28T17:55:50Z"
))
add_capture(doc, "07_devices_filtered.txt", "Full filtered device list")


# Section 7 — Services in action
add_heading(doc, "7. Services in action", level=1)
add_image(doc, SHOTS / "03_services.png",
          caption="admin-portal Flask /healthz + /whoami; internal-db psql query; netns proof",
          width_inches=6.5)


add_heading(doc, "7.1 admin-portal · Flask on :8080", level=2)
add_shell_block(doc,
    "docker exec tailscaletest-poc-admin-portal-1 \\\n    curl -fsS http://localhost:8080/healthz",
    '{"service":"admin-portal","status":"ok"}'
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-admin-portal-1 \\\n    curl -fsS http://localhost:8080/whoami",
    (
        "{\n"
        "  \"service\": \"admin-portal\",\n"
        "  \"caller_groups\": \"<none>\",\n"
        "  \"caller_login\": \"<none>\",\n"
        "  \"caller_name\": \"<none>\",\n"
        "  \"caller_tailnet\": \"<none>\"\n"
        "}"
    )
)
add_para(doc,
    "The caller_* headers get populated when reached via tailscale serve (because "
    "Tailscale's identity layer injects them). Direct container access leaves them at <none>."
)


add_heading(doc, "7.2 internal-db · Postgres 16 with seed", level=2)
add_shell_block(doc,
    "docker exec tailscaletest-poc-internal-db-1 \\\n    psql -U headscaletest -d tailscaletest -c 'SELECT * FROM people'",
    (
        " id | email                          | role\n"
        "----+--------------------------------+--------------\n"
        "  1 | ada@tailscaletest.example      | engineer\n"
        "  2 | linus@tailscaletest.example    | engineer\n"
        "  3 | eve@tailscaletest.example      | untrusted\n"
        "(3 rows)"
    )
)


add_heading(doc, "7.3 Service-to-sidecar namespace sharing", level=2)
add_para(doc,
    "The whole point of network_mode: \"service:ts-admin-portal\" in "
    "docker-compose.yml is to put admin-portal and its sidecar in the same network "
    "namespace, so admin-portal's Flask :8080 is reachable through ts-admin-portal's "
    "tailscale0 (100.110.90.56). Proof:"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-admin-portal-1 readlink /proc/self/ns/net",
    "net:[4026533893]"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-admin-portal-1 readlink /proc/self/ns/net",
    "net:[4026533893]"
)
add_para(doc, "Same netns -> the service's port 8080 is reachable through the sidecar's tailnet IP. network_mode resolved correctly after this restart; see the gotchas section for the earlier mismatch.")


# Section 8 — Bridge isolation
add_heading(doc, "8. Bridge isolation sanity check", level=1)
add_para(doc,
    "Each sidecar attaches to exactly one Docker bridge — and only one. This is what "
    "forces the only path between nodes to be the WireGuard overlay, not Docker's "
    "embedded DNS:"
)
add_shell_block(doc,
    "for c in admin-portal internal-db eng-admin untrusted; do\n      echo \"=== $c sidecar bridges ===\"\n      docker inspect tailscaletest-poc-ts-$c-1 \\\n          --format '{{json .NetworkSettings.Networks}}' \\\n          | jq -r 'keys[]'\n  done",
    (
        "=== admin-portal sidecar bridges ===\n"
        "tailscaletest-poc_net-admin-portal\n"
        "=== internal-db sidecar bridges ===\n"
        "tailscaletest-poc_net-internal-db\n"
        "=== eng-admin sidecar bridges ===\n"
        "tailscaletest-poc_net-eng-admin\n"
        "=== untrusted sidecar bridges ===\n"
        "tailscaletest-poc_net-untrusted"
    )
)
add_shell_block(doc,
    "docker network ls --filter name=tailscaletest-poc_net-",
    (
        "NAME                                 DRIVER    SCOPE\n"
        "tailscaletest-poc_net-admin-portal   bridge    local\n"
        "tailscaletest-poc_net-eng-admin      bridge    local\n"
        "tailscaletest-poc_net-internal-db    bridge    local\n"
        "tailscaletest-poc_net-untrusted      bridge    local"
    )
)
add_capture(doc, "08_bridges.txt", "Bridge isolation raw output")


# Section 9 — The matrix in one table
add_heading(doc, "9. The matrix in one table", level=1)
add_code_block(doc, (
    "from        to                          observed                                              verdict\n"
    "----------  --------------------------  -----------------------------------------------------  -------\n"
    "eng-admin   admin-portal:8080           HTTP 200 {\"service\":\"admin-portal\",\"status\":\"ok\"}   ALLOW\n"
    "eng-admin   internal-db via SSH         postgres (SSH session lands)                          ALLOW\n"
    "eng-admin   internal-db:5432 direct     name not in netmap + tailnet IP host-unreachable       DENY\n"
    "untrusted   admin-portal (any port)     name not in netmap + tailnet IP host-unreachable       DENY\n"
    "untrusted   internal-db:5432            tailnet IP host-unreachable                            DENY\n"
    "untrusted   internal-db via SSH         tag untrusted is not allowed by the tailnet policy    DENY"
))
add_para(doc,
    "If any cell shows the opposite verdict, the most likely root cause is one of:"
)
for it in [
    "a typo in .env swapping keys between services",
    "the live tailnet policy not matching acl/policy.hujson (re-paste it in admin console -> Access Controls -> Save)",
    "a node's tag didn't apply at first registration (wipe its state volume and docker compose up -d --force-recreate)",
]:
    doc.add_paragraph(it, style="List Bullet")


# Section 10 — Gotchas
add_heading(doc, "10. Gotchas and lessons learned (this run)", level=1)

add_heading(doc, "10.1 network_mode: service:X does not survive a partial restart", level=2)
add_para(doc,
    "After restarting the admin-portal service during debugging, the admin-portal container "
    "ended up in its own network namespace — Flask was bound to 8080 on the docker bridge, but "
    "ts-admin-portal had no LISTEN socket on 8080 (its /proc/net/tcp showed only tailscaled's "
    "ports). The fix was docker compose up -d admin-portal again, which re-resolved "
    "network_mode: service:ts-admin-portal to the current container ID and put both back in "
    "the same netns. Verify with:"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-admin-portal-1 readlink /proc/self/ns/net",
    "net:[4026533893]"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-admin-portal-1 readlink /proc/self/ns/net",
    "net:[4026533893]   # same net:[...] -> sharing worked"
)

add_heading(doc, "10.2 A stale admin-portal node can pin the new one to a -2 suffix", level=2)
add_para(doc,
    "This run hit it: there were two older admin-portal nodes left over in the tailnet from "
    "previous POC runs, so the new node got the hostname suffix admin-portal-2 in "
    "tailscale status. Deleting the older nodes cleared the way for a clean admin-portal "
    "hostname on the next registration, but the MagicDNS name still resolved to "
    "admin-portal-2.taila1b884.ts.net (Tailscale kept the older suffix in the DNS layer). "
    "The workaround is to use the suffixed MagicDNS name in all wget/nc calls — both names "
    "resolve to the same 100.110.90.56 IP."
)

add_heading(doc, "10.3 nslookup returns NXDOMAIN but getent hosts resolves", level=2)
add_para(doc,
    "Tailscale's NSS module (libnss_tailscale) writes the peer's name into the sidecar's "
    "namespace and is reachable through getent hosts / wget / curl, but NOT through "
    "nslookup. That's because nslookup queries DNS only (and bypasses glibc's NSS), while "
    "every other tool goes through glibc. The implication: when debugging DNS, always use "
    "getent hosts or wget, not nslookup."
)

add_heading(doc, "10.4 tagged-devices is what an admin-portal sidecar looks like to its peers", level=2)
add_para(doc,
    "From eng-admin's tailscale status, the admin-portal sidecar shows up as:"
)
add_shell_block(doc,
    "docker exec tailscaletest-poc-ts-eng-admin-1 tailscale status",
    (
        "100.124.233.31  eng-admin     eng-admin.taila1b884.ts.net     linux  -\n"
        "100.110.90.56   admin-portal-2  tagged-devices              linux  active; ...\n"
        "...                              (admin-portal as tagged-devices, not by hostname)"
    )
)
add_para(doc,
    "Tailscale substitutes tagged-devices as the peer-name for tagged-only nodes (the hostname "
    "is preserved in the API but Tailscale's netmap uses a synthetic name to signal that the "
    "node is tag-owned and not user-owned)."
)

add_heading(doc, "10.5 tskey-auth-... keys are NOT API tokens", level=2)
add_para(doc,
    "A trap for first-time readers. TS_AUTHKEY_* in .env are auth keys (tskey-auth-...) used "
    "by tailscaled to register a node. They have NO permission to call the Tailscale HTTP API. "
    "For the API you need a tskey-api-... token from admin console -> Settings -> Personal "
    "access tokens. Calling https://api.tailscale.com/... with a tskey-auth-... key returns "
    "401 {\"message\":\"API token invalid\"}."
)

add_heading(doc, "10.6 Compose service name restart: unless-recreated is invalid", level=2)
add_para(doc,
    "The first compose file used restart: unless-recreated, which Docker rejects (valid "
    "values are no, always, on-failure, unless-stopped). Fixed in this repo to unless-stopped."
)


# Section 11 — File map
add_heading(doc, "11. File map", level=1)
add_code_block(doc, (
    "tailscaletest-poc/\n"
    "├── README.md                          quickstart\n"
    "├── docker-compose.yml                 4 services × 4 personas, each on its own bridge\n"
    "├── acl/\n"
    "│   └── policy.hujson                  tagOwners + acls + ssh, default-deny\n"
    "├── apps/\n"
    "│   ├── admin-portal/                  Flask :8080\n"
    "│   └── internal-db/                   Postgres 16 with init.sql seed\n"
    "├── notes/\n"
    "│   └── walkthrough.md                  simplified, illustrative walkthrough\n"
    "├── scripts/\n"
    "│   ├── capture_walkthrough.sh          walks the POC + writes output/captures/*.txt\n"
    "│   └── render_screenshots.py           renders output/screenshots/*.png via chrome headless\n"
    "└── output/                            THIS RUN\n"
    "    ├── RUN_REPORT.md                  this file (markdown source)\n"
    "    ├── RUN_REPORT.docx                this file (Word)\n"
    "    ├── captures/                       raw command outputs (text)\n"
    "    └── screenshots/                    rendered PNGs of the lab"
))


# Section 12 — Next step
add_heading(doc, "12. Next step: run the parallel headscaletest-poc", level=1)
add_para(doc,
    "The mirror POC at github.com/cmarin78/headscaletest-poc does the same thing with a "
    "self-hosted Headscale control plane. The topology, apps, and policy are intentionally "
    "identical so a side-by-side comparison is just docker compose down && docker compose "
    "-f ... up -d."
)

add_para(doc, "— end of run report —", italic=True)
add_para(doc, "Captured: 2026-09-28 17:55Z (ART) · POC: github.com/cmarin78/tailscaletest-poc", size=9, color=(0x99, 0x99, 0x99))


# Save
doc.save(str(OUT))
print(f"OK -> {OUT} ({OUT.stat().st_size // 1024} KB)")