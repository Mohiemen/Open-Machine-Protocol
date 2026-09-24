"""Host posture audit - the Required items of Hardening Guide section 3.

The guide says `omp-gateway audit-host` "runs these checks and reports
drift". Both halves matter. A one-off pass on commissioning day tells you
nothing six months later, when someone has installed Grafana "just for a
minute" and turned password SSH back on to debug it. So every check records
the evidence it saw, the evidence is stored as a baseline, and later runs
say what CHANGED as well as what is wrong now.

Honesty rule, same as the DPP audit tool: a check that cannot be evaluated
reports UNKNOWN and never collapses into a pass. Most of these checks read
files that simply do not exist on a container or a developer laptop; saying
"ok" there would be a lie that gets copied into a compliance answer.
"""
from __future__ import annotations

import json
import pathlib
import re
import stat
import subprocess
from dataclasses import dataclass, field

OK, FAIL, UNKNOWN = "ok", "fail", "unknown"
REQUIRED, RECOMMENDED = "required", "recommended"

# Services that would make the box not a dedicated gateway. A broker is
# deliberately absent: Hardening Guide s5 permits a gateway-local broker.
_CO_TENANTS = (
    "grafana", "influxdb", "node-red", "nodered", "docker", "containerd",
    "postgres", "mysql", "mariadb", "apache2", "httpd", "nginx", "k3s",
    "kubelet", "jenkins", "plex", "samba", "smbd",
)


@dataclass
class Check:
    id: str
    requirement: str          # required | recommended
    status: str               # ok | fail | unknown
    detail: str
    evidence: dict = field(default_factory=dict)
    guide: str = ""           # the Hardening Guide clause this comes from


@dataclass
class Host:
    """What the checks are allowed to look at.

    `root` prefixes every path, so tests build a whole fake host in a tmpdir
    and the real run passes "/". `commands` lets a test supply output for
    the handful of things no file answers.
    """

    root: pathlib.Path = pathlib.Path("/")
    service_user: str = "omp"
    commands: dict[str, str | None] | None = None

    def path(self, absolute: str) -> pathlib.Path:
        return self.root / absolute.lstrip("/")

    def read(self, absolute: str) -> str | None:
        p = self.path(absolute)
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            return None

    def glob(self, absolute: str, pattern: str) -> list[pathlib.Path]:
        d = self.path(absolute)
        return sorted(d.glob(pattern)) if d.is_dir() else []

    def command(self, key: str) -> str | None:
        """Output of one whitelisted command, or None if unavailable."""
        if self.commands is not None:
            return self.commands.get(key)
        argv = _COMMANDS.get(key)
        if argv is None or self.root != pathlib.Path("/"):
            return None
        try:
            out = subprocess.run(argv, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout if out.returncode == 0 else None


_COMMANDS = {
    "timedatectl": ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
}


# -- individual checks --------------------------------------------------
def _sshd_settings(host: Host) -> dict[str, str] | None:
    """Effective sshd directives; later files and later lines win, which is
    how sshd_config.d drop-ins actually behave for most distro layouts."""
    texts = []
    main = host.read("/etc/ssh/sshd_config")
    if main is not None:
        texts.append(main)
    for p in host.glob("/etc/ssh/sshd_config.d", "*.conf"):
        try:
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    if not texts:
        return None
    settings: dict[str, str] = {}
    for text in texts:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"[\s=]+", line, maxsplit=1)
            if len(parts) == 2:
                settings[parts[0].lower()] = parts[1].strip().split()[0].lower()
    return settings


def check_ssh(host: Host) -> Check:
    s = _sshd_settings(host)
    if s is None:
        return Check("ssh", REQUIRED, UNKNOWN,
                     "no sshd_config found - if this host runs sshd, the audit "
                     "could not see its policy", guide="s3")
    problems = []
    if s.get("passwordauthentication", "yes") != "no":
        problems.append("password auth is not disabled")
    if s.get("kbdinteractiveauthentication",
             s.get("challengeresponseauthentication", "yes")) != "no":
        problems.append("keyboard-interactive auth is not disabled")
    if s.get("permitrootlogin", "prohibit-password") != "no":
        problems.append(f"root login is '{s.get('permitrootlogin', 'default')}'")
    if s.get("pubkeyauthentication", "yes") != "yes":
        problems.append("public-key auth is disabled")
    evidence = {k: s.get(k) for k in (
        "passwordauthentication", "permitrootlogin", "pubkeyauthentication",
        "kbdinteractiveauthentication", "listenaddress", "allowusers")}
    if problems:
        return Check("ssh", REQUIRED, FAIL, "; ".join(problems), evidence, "s3")
    reach = ("admin-subnet restriction not visible to this audit "
             "(no ListenAddress/AllowUsers) - confirm at the firewall"
             if not (s.get("listenaddress") or s.get("allowusers")) else
             "key-only, no root login")
    return Check("ssh", REQUIRED, OK, reach, evidence, "s3")


def check_unattended_upgrades(host: Host) -> Check:
    periodic = host.read("/etc/apt/apt.conf.d/20auto-upgrades")
    if periodic is None and not host.path("/etc/apt").is_dir():
        return Check("unattended_upgrades", REQUIRED, UNKNOWN,
                     "not an apt system - verify this distribution's automatic "
                     "security updates by hand", guide="s3")
    if periodic is None:
        return Check("unattended_upgrades", REQUIRED, FAIL,
                     "no /etc/apt/apt.conf.d/20auto-upgrades - automatic "
                     "security updates are not configured", guide="s3")
    on = re.search(r'Unattended-Upgrade"?\s+"1"', periodic) is not None
    evidence = {"20auto-upgrades": periodic.strip()}
    if not on:
        return Check("unattended_upgrades", REQUIRED, FAIL,
                     "Unattended-Upgrade is not set to 1", evidence, "s3")
    return Check("unattended_upgrades", REQUIRED, OK,
                 "unattended-upgrades enabled", evidence, "s3")


def _unit_text(host: Host) -> tuple[str | None, str]:
    for where in ("/etc/systemd/system/omp-gateway.service",
                  "/lib/systemd/system/omp-gateway.service",
                  "/usr/lib/systemd/system/omp-gateway.service"):
        text = host.read(where)
        if text is not None:
            return text, where
    return None, ""


def check_service_user(host: Host) -> Check:
    text, where = _unit_text(host)
    if text is None:
        return Check("service_user", REQUIRED, UNKNOWN,
                     "no omp-gateway.service unit found - cannot tell which "
                     "user the gateway runs as", guide="s3")
    m = re.search(r"^\s*User\s*=\s*(\S+)", text, re.M)
    user = m.group(1) if m else None
    evidence = {"unit": where, "User": user}
    if user is None:
        return Check("service_user", REQUIRED, FAIL,
                     f"{where} sets no User=, so the service runs as root",
                     evidence, "s3")
    if user == "root":
        return Check("service_user", REQUIRED, FAIL,
                     "service runs as root - fix the udev rule instead "
                     "(docs/security/examples/99-omp-serial.rules)",
                     evidence, "s3")
    return Check("service_user", REQUIRED, OK, f"runs as {user}", evidence, "s3")


def _groups_of(host: Host, user: str) -> set[str] | None:
    text = host.read("/etc/group")
    if text is None:
        return None
    groups = set()
    for line in text.splitlines():
        fields = line.split(":")
        if len(fields) >= 4 and user in [m for m in fields[3].split(",") if m]:
            groups.add(fields[0])
    return groups


def check_serial_access(host: Host) -> Check:
    """Device-group access, not root. The udev rule is how you get it."""
    rule = host.read("/etc/udev/rules.d/99-omp-serial.rules")
    groups = _groups_of(host, host.service_user)
    evidence = {"udev_rule": rule is not None,
                "groups": sorted(groups) if groups is not None else None}
    if groups is None:
        return Check("serial_access", REQUIRED, UNKNOWN,
                     "no /etc/group readable - cannot tell what device access "
                     f"{host.service_user} has", evidence, "s3")
    device_groups = groups & {"dialout", "plugdev", "omp-serial", "tty", "uucp"}
    if not device_groups and rule is None:
        return Check("serial_access", REQUIRED, FAIL,
                     f"{host.service_user} is in no serial device group and no "
                     "99-omp-serial.rules is installed - a serial adapter here "
                     "can only work by running as root", evidence, "s3")
    if not device_groups:
        return Check("serial_access", REQUIRED, UNKNOWN,
                     "udev rule installed but the service user is in no device "
                     "group - check the rule grants the group it is in",
                     evidence, "s3")
    return Check("serial_access", REQUIRED, OK,
                 f"{host.service_user} in {', '.join(sorted(device_groups))}",
                 evidence, "s3")


def check_dedicated_device(host: Host) -> Check:
    """Heuristic by nature: we can see what is enabled, not what it is for.

    So a hit is a FAIL with the unit named (the operator can judge), and a
    miss is UNKNOWN rather than OK - absence of a known co-tenant is not
    proof the box is dedicated.
    """
    wants = host.path("/etc/systemd/system/multi-user.target.wants")
    if not wants.is_dir():
        return Check("dedicated_device", REQUIRED, UNKNOWN,
                     "no systemd target wants directory - cannot enumerate "
                     "what else runs on this host", guide="s3")
    units = sorted(p.name for p in wants.iterdir())
    found = sorted({u for u in units
                    if any(t in u.lower() for t in _CO_TENANTS)})
    evidence = {"enabled_units": units, "co_tenants": found}
    if found:
        return Check("dedicated_device", REQUIRED, FAIL,
                     "shares the host with " + ", ".join(found), evidence, "s3")
    return Check("dedicated_device", REQUIRED, UNKNOWN,
                 f"no known co-tenant among {len(units)} enabled unit(s) - "
                 "confirm by eye; this check only knows common ones",
                 evidence, "s3")


def check_key_permissions(host: Host, state_dir: pathlib.Path | None) -> Check:
    """Hardening Guide s4: the keypair stays on the gateway, and only the
    gateway's user can read it."""
    if state_dir is None:
        return Check("key_permissions", REQUIRED, UNKNOWN,
                     "no --state-dir given - key file not inspected", guide="s4")
    key = pathlib.Path(state_dir) / "keys" / "gateway.pem"
    if not key.exists():
        return Check("key_permissions", REQUIRED, UNKNOWN,
                     f"no keypair at {key} - this gateway is not signing",
                     {"path": str(key)}, "s4")
    mode = stat.S_IMODE(key.stat().st_mode)
    evidence = {"path": str(key), "mode": oct(mode)}
    if mode & 0o077:
        return Check("key_permissions", REQUIRED, FAIL,
                     f"{key} is mode {oct(mode)}; must be 0600 - anyone who "
                     "reads it can fabricate this gateway's history",
                     evidence, "s4")
    return Check("key_permissions", REQUIRED, OK, f"{key} is {oct(mode)}",
                 evidence, "s4")


def check_ntp(host: Host) -> Check:
    """Recommended, s4: "ntp_synced" is worth having true."""
    if host.path("/run/systemd/timesync/synchronized").exists():
        return Check("ntp", RECOMMENDED, OK, "clock synchronised",
                     {"source": "systemd-timesyncd"}, "s4")
    out = host.command("timedatectl")
    if out is None:
        return Check("ntp", RECOMMENDED, UNKNOWN,
                     "no timedatectl and no timesync marker - clock confidence "
                     "unverified", guide="s4")
    synced = out.strip().lower() in ("yes", "true", "1")
    evidence = {"NTPSynchronized": out.strip()}
    if not synced:
        return Check("ntp", RECOMMENDED, FAIL,
                     "clock is not NTP-synchronised; timestamps and the "
                     "ntp_synced verification flag cannot be trusted",
                     evidence, "s4")
    return Check("ntp", RECOMMENDED, OK, "clock synchronised", evidence, "s4")


def run_checks(host: Host | None = None,
               state_dir: pathlib.Path | str | None = None) -> list[Check]:
    host = host or Host()
    state = pathlib.Path(state_dir) if state_dir else None
    return [
        check_dedicated_device(host),
        check_ssh(host),
        check_unattended_upgrades(host),
        check_service_user(host),
        check_serial_access(host),
        check_key_permissions(host, state),
        check_ntp(host),
    ]


# -- drift ---------------------------------------------------------------
BASELINE_NAME = "host-audit-baseline.json"


def to_baseline(checks: list[Check]) -> dict:
    return {c.id: {"status": c.status, "evidence": c.evidence} for c in checks}


def load_baseline(state_dir: pathlib.Path | str | None) -> dict | None:
    if state_dir is None:
        return None
    p = pathlib.Path(state_dir) / BASELINE_NAME
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_baseline(state_dir: pathlib.Path | str, checks: list[Check]) -> pathlib.Path:
    p = pathlib.Path(state_dir) / BASELINE_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_baseline(checks), indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p


def drift(baseline: dict, checks: list[Check]) -> list[str]:
    """What changed since the baseline. Evidence changes count even when the
    verdict does not: SSH going from AllowUsers ops to AllowUsers ops,contractor
    is still a pass, and is still something the weekly rhythm should surface."""
    lines = []
    current = to_baseline(checks)
    for cid, now in current.items():
        was = baseline.get(cid)
        if was is None:
            lines.append(f"{cid}: new check, now {now['status'].upper()}")
            continue
        if was.get("status") != now["status"]:
            lines.append(f"{cid}: {str(was.get('status')).upper()} -> "
                         f"{now['status'].upper()}")
        elif was.get("evidence") != now["evidence"]:
            changed = sorted(
                k for k in set(was.get("evidence") or {}) | set(now["evidence"])
                if (was.get("evidence") or {}).get(k) != now["evidence"].get(k))
            lines.append(f"{cid}: still {now['status'].upper()}, but "
                         f"{', '.join(changed)} changed")
    for cid in baseline:
        if cid not in current:
            lines.append(f"{cid}: check no longer run")
    return lines


# -- reporting -----------------------------------------------------------
_MARK = {OK: "✔", FAIL: "✖", UNKNOWN: "?"}


def format_report(checks: list[Check], drift_lines: list[str] | None = None,
                  baseline_seen: bool = False) -> str:
    out = ["Host audit - Hardening Guide s3 (Required) and s4"]
    for c in checks:
        tag = "[Required]" if c.requirement == REQUIRED else "[Recommended]"
        out.append(f"  {_MARK[c.status]} {c.id:<20} {tag} {c.detail}")
    req_fail = [c for c in checks if c.requirement == REQUIRED and c.status == FAIL]
    req_unknown = [c for c in checks
                   if c.requirement == REQUIRED and c.status == UNKNOWN]
    out.append("")
    out.append(f"{len(req_fail)} Required check(s) failing, "
               f"{len(req_unknown)} not evaluable "
               f"(not evaluable is not the same as passing)")
    out.append("not checked from here: network segmentation (s2), broker ACLs "
               "and TLS config (s5), release verification (s6) - review those "
               "by hand; see docs/security/examples/")
    if not baseline_seen:
        out.append("no baseline stored yet - re-run with --save-baseline to "
                   "make later runs report drift")
    elif drift_lines:
        out.append(f"drift since baseline ({len(drift_lines)}):")
        out.extend(f"  ! {line}" for line in drift_lines)
    else:
        out.append("no drift since baseline")
    return "\n".join(out)
