"""Inject self-hosted RustDesk server settings before building.

Runs on the GitHub Actions Windows runner right after checkout.
Values come from repository secrets (never stored in the repository itself).
"""
import io
import os
import re
import sys

ID_SERVER = os.environ.get("RD_ID_SERVER", "").strip()
API_SERVER = os.environ.get("RD_API_SERVER", "").strip()
PUB_KEY = os.environ.get("RD_KEY", "").strip()
PASSWORD = os.environ.get("RD_PASSWORD", "").strip()

missing = [
    name
    for name, value in (
        ("RD_ID_SERVER", ID_SERVER),
        ("RD_API_SERVER", API_SERVER),
        ("RD_KEY", PUB_KEY),
        ("RD_PASSWORD", PASSWORD),
    )
    if not value
]
if missing:
    sys.exit("missing required secret(s): " + ", ".join(missing))

cfg_path = "libs/hbb_common/src/config.rs"
common_path = "src/common.rs"
cfg = io.open(cfg_path, encoding="utf-8").read()
common = io.open(common_path, encoding="utf-8").read()

if (
    ID_SERVER in cfg
    and PUB_KEY in cfg
    and 'map.insert("password"' in cfg
    and API_SERVER in common
):
    print("already patched, nothing to do")
    sys.exit(0)

cfg, n_servers = re.subn(
    r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];',
    'pub const RENDEZVOUS_SERVERS: &[&str] = &["%s"];' % ID_SERVER,
    cfg,
    count=1,
)
cfg, n_key = re.subn(
    r'pub const RS_PUB_KEY: &str = "[^"]*";',
    'pub const RS_PUB_KEY: &str = "%s";' % PUB_KEY,
    cfg,
    count=1,
)
hard_settings = (
    "pub static ref HARD_SETTINGS: RwLock<HashMap<String, String>> = {\n"
    "        let mut map = HashMap::new();\n"
    '        map.insert("password".to_string(), "%s".to_string());\n'
    "        RwLock::new(map)\n"
    "    };" % PASSWORD
)
cfg, n_hard = re.subn(
    r"pub static ref HARD_SETTINGS: RwLock<HashMap<String, String>> = Default::default\(\);",
    lambda _m: hard_settings,
    cfg,
    count=1,
)

if not (n_servers and n_key and n_hard):
    sys.exit(
        "patch anchors not found: servers=%d key=%d hard_settings=%d"
        % (n_servers, n_key, n_hard)
    )

io.open(cfg_path, "w", encoding="utf-8", newline="\n").write(cfg)

common_new = common.replace(
    '"https://admin.rustdesk.com".to_owned()',
    '"%s".to_owned()' % API_SERVER,
)
if common_new == common:
    sys.exit("api server anchor not found in src/common.rs")
io.open(common_path, "w", encoding="utf-8", newline="\n").write(common_new)

print("== injected settings ==")
print("RENDEZVOUS_SERVERS:", ID_SERVER)
print("API fallback:", API_SERVER)
print("RS_PUB_KEY length:", len(PUB_KEY))
print("hard password length:", len(PASSWORD))
for path, needle in (
    (cfg_path, 'pub const RENDEZVOUS_SERVERS'),
    (cfg_path, 'pub const RS_PUB_KEY'),
    (cfg_path, 'map.insert("password"'),
    (common_path, API_SERVER),
):
    text = io.open(path, encoding="utf-8").read()
    if needle not in text:
        sys.exit("verification failed: %s missing in %s" % (needle, path))
print("verification OK")
