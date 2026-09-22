"""omp-gateway audit-host - Hardening Guide s3 checks and drift reporting.

Every check is exercised against a fake host tree, because the interesting
cases (root login enabled, Grafana installed alongside, a world-readable
keypair) are exactly the ones you cannot create on the machine running the
tests. The property under most scrutiny is that "cannot tell" never reports
as "fine".
"""
import io
import json
from contextlib import redirect_stdout

import pytest
from omp.cli import main as cli_main
from omp.core import hostaudit as ha


def good_host(tmp_path, *, root_login="no", password_auth="no"):
    root = tmp_path / "host"
    (root / "etc/ssh").mkdir(parents=True)
    (root / "etc/ssh/sshd_config").write_text(
        f"PermitRootLogin {root_login}\n"
        f"PasswordAuthentication {password_auth}\n"
        "KbdInteractiveAuthentication no\n"
        "PubkeyAuthentication yes\n"
        "AllowUsers ops\n")
    (root / "etc/apt/apt.conf.d").mkdir(parents=True)
    (root / "etc/apt/apt.conf.d/20auto-upgrades").write_text(
        'APT::Periodic::Update-Package-Lists "1";\n'
        'APT::Periodic::Unattended-Upgrade "1";\n')
    (root / "etc/systemd/system").mkdir(parents=True)
    (root / "etc/systemd/system/omp-gateway.service").write_text(
        "[Service]\nUser=omp\nExecStart=/usr/bin/omp-gateway run\n")
    wants = root / "etc/systemd/system/multi-user.target.wants"
    wants.mkdir()
    (wants / "omp-gateway.service").write_text("")
    (wants / "ssh.service").write_text("")
    (root / "etc/group").write_text(
        "root:x:0:\nomp-serial:x:995:omp\ndialout:x:20:omp\n")
    (root / "etc/udev/rules.d").mkdir(parents=True)
    (root / "etc/udev/rules.d/99-omp-serial.rules").write_text(
        'SUBSYSTEM=="tty", GROUP="omp-serial", MODE="0660"\n')
    return ha.Host(root=root, commands={"timedatectl": "yes"})


def state_with_key(tmp_path, mode=0o600):
    state = tmp_path / "state"
    (state / "keys").mkdir(parents=True)
    key = state / "keys" / "gateway.pem"
    key.write_text("-----BEGIN PRIVATE KEY-----\nfake\n")
    key.chmod(mode)
    return state


def by_id(checks):
    return {c.id: c for c in checks}


def test_clean_host_passes_every_required_check_it_can_evaluate(tmp_path):
    state = state_with_key(tmp_path)
    checks = by_id(ha.run_checks(good_host(tmp_path), state))
    for cid in ("ssh", "unattended_upgrades", "service_user", "serial_access",
                "key_permissions", "ntp"):
        assert checks[cid].status == ha.OK, (cid, checks[cid].detail)
    # ... except the one that is honest about being a heuristic
    assert checks["dedicated_device"].status == ha.UNKNOWN


@pytest.mark.parametrize("kwargs,detail", [
    ({"root_login": "yes"}, "root login"),
    ({"root_login": "prohibit-password"}, "root login"),
    ({"password_auth": "yes"}, "password auth"),
])
def test_ssh_policy_failures(tmp_path, kwargs, detail):
    c = ha.check_ssh(good_host(tmp_path, **kwargs))
    assert c.status == ha.FAIL and detail in c.detail


def test_sshd_config_d_dropin_overrides_the_main_file(tmp_path):
    host = good_host(tmp_path)
    d = host.root / "etc/ssh/sshd_config.d"
    d.mkdir()
    (d / "50-cloud-init.conf").write_text("PasswordAuthentication yes\n")
    c = ha.check_ssh(host)
    assert c.status == ha.FAIL and "password auth" in c.detail


def test_missing_sshd_config_is_unknown_not_ok(tmp_path):
    host = good_host(tmp_path)
    (host.root / "etc/ssh/sshd_config").unlink()
    assert ha.check_ssh(host).status == ha.UNKNOWN


def test_unattended_upgrades_off_fails_and_non_apt_is_unknown(tmp_path):
    host = good_host(tmp_path)
    f = host.root / "etc/apt/apt.conf.d/20auto-upgrades"
    f.write_text('APT::Periodic::Unattended-Upgrade "0";\n')
    assert ha.check_unattended_upgrades(host).status == ha.FAIL
    f.unlink()
    assert ha.check_unattended_upgrades(host).status == ha.FAIL
    import shutil
    shutil.rmtree(host.root / "etc/apt")
    assert ha.check_unattended_upgrades(host).status == ha.UNKNOWN


def test_service_running_as_root_fails_and_points_at_the_udev_rule(tmp_path):
    host = good_host(tmp_path)
    unit = host.root / "etc/systemd/system/omp-gateway.service"
    unit.write_text("[Service]\nUser=root\n")
    c = ha.check_service_user(host)
    assert c.status == ha.FAIL and "udev" in c.detail
    # no User= at all is the same failure, less obviously
    unit.write_text("[Service]\nExecStart=/usr/bin/omp-gateway run\n")
    assert ha.check_service_user(host).status == ha.FAIL


def test_serial_access_without_group_or_rule_fails(tmp_path):
    host = good_host(tmp_path)
    (host.root / "etc/group").write_text("root:x:0:\n")
    (host.root / "etc/udev/rules.d/99-omp-serial.rules").unlink()
    assert ha.check_serial_access(host).status == ha.FAIL


def test_co_tenant_service_fails_the_dedicated_device_check(tmp_path):
    host = good_host(tmp_path)
    wants = host.root / "etc/systemd/system/multi-user.target.wants"
    (wants / "grafana-server.service").write_text("")
    c = ha.check_dedicated_device(host)
    assert c.status == ha.FAIL and "grafana-server.service" in c.detail


def test_local_broker_is_not_a_co_tenant(tmp_path):
    """Hardening Guide s5 permits a gateway-local broker, so flagging it
    would train operators to ignore this check."""
    host = good_host(tmp_path)
    wants = host.root / "etc/systemd/system/multi-user.target.wants"
    (wants / "mosquitto.service").write_text("")
    assert ha.check_dedicated_device(host).status != ha.FAIL


def test_world_readable_key_fails(tmp_path):
    state = state_with_key(tmp_path, mode=0o644)
    c = ha.check_key_permissions(ha.Host(root=tmp_path / "host"), state)
    assert c.status == ha.FAIL and "0600" in c.detail


def test_absent_key_is_unknown_not_ok(tmp_path):
    (tmp_path / "state").mkdir()
    c = ha.check_key_permissions(ha.Host(), tmp_path / "state")
    assert c.status == ha.UNKNOWN


def test_unsynced_clock_fails_recommended_only(tmp_path):
    host = good_host(tmp_path)
    host.commands = {"timedatectl": "no"}
    c = ha.check_ntp(host)
    assert c.status == ha.FAIL and c.requirement == ha.RECOMMENDED


def test_empty_host_yields_unknowns_and_never_a_pass(tmp_path):
    """The dangerous failure mode: auditing a host where nothing is readable
    and getting a clean bill of health."""
    (tmp_path / "empty").mkdir()
    checks = ha.run_checks(ha.Host(root=tmp_path / "empty", commands={}), None)
    assert all(c.status == ha.UNKNOWN for c in checks)
    assert not any(c.status == ha.OK for c in checks)
    report = ha.format_report(checks)
    assert "not evaluable is not the same as passing" in report


# -- drift ---------------------------------------------------------------
def test_drift_reports_status_changes(tmp_path):
    host = good_host(tmp_path)
    before = ha.run_checks(host, None)
    baseline = ha.to_baseline(before)
    (host.root / "etc/ssh/sshd_config").write_text(
        "PermitRootLogin yes\nPasswordAuthentication yes\n")
    after = ha.run_checks(host, None)
    lines = ha.drift(baseline, after)
    assert any(line.startswith("ssh: OK -> FAIL") for line in lines)


def test_drift_reports_evidence_change_even_when_the_verdict_holds(tmp_path):
    host = good_host(tmp_path)
    baseline = ha.to_baseline(ha.run_checks(host, None))
    (host.root / "etc/ssh/sshd_config").write_text(
        "PermitRootLogin no\nPasswordAuthentication no\n"
        "KbdInteractiveAuthentication no\nPubkeyAuthentication yes\n"
        "AllowUsers ops,contractor\n")
    lines = ha.drift(baseline, ha.run_checks(host, None))
    assert lines and "still OK" in lines[0] and "allowusers" in lines[0]


def test_no_drift_when_nothing_changed(tmp_path):
    host = good_host(tmp_path)
    baseline = ha.to_baseline(ha.run_checks(host, None))
    assert ha.drift(baseline, ha.run_checks(host, None)) == []


# -- CLI -----------------------------------------------------------------
def run_cli(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(list(argv))
    return code, buf.getvalue()


def test_cli_exit_codes_clean_drift_and_required_failure(tmp_path):
    host = good_host(tmp_path)
    state = state_with_key(tmp_path)
    base = ["audit-host", "--root", str(host.root), "--state-dir", str(state)]

    code, out = run_cli(*base, "--save-baseline")
    assert code == 0 and "baseline written" in out
    assert (state / ha.BASELINE_NAME).exists()

    code, out = run_cli(*base)
    assert code == 0 and "no drift since baseline" in out

    (host.root / "etc/ssh/sshd_config").write_text("PermitRootLogin yes\n")
    code, out = run_cli(*base)
    assert code == 2                      # Required failing outranks drift
    assert "drift since baseline" in out and "ssh: OK -> FAIL" in out


def test_cli_returns_1_for_drift_alone(tmp_path):
    host = good_host(tmp_path)
    state = state_with_key(tmp_path)
    base = ["audit-host", "--root", str(host.root), "--state-dir", str(state)]
    run_cli(*base, "--save-baseline")
    # a new enabled unit: still no Required failure, but the host moved
    (host.root / "etc/systemd/system/multi-user.target.wants"
     / "tailscaled.service").write_text("")
    code, out = run_cli(*base)
    assert code == 1 and "drift since baseline" in out


def test_cli_strict_unknown_fails_on_unevaluable_required_checks(tmp_path):
    (tmp_path / "empty").mkdir()
    args = ["audit-host", "--root", str(tmp_path / "empty")]
    assert run_cli(*args)[0] == 0
    assert run_cli(*args, "--strict-unknown")[0] == 2


def test_cli_json_output_is_machine_readable(tmp_path):
    host = good_host(tmp_path)
    code, out = run_cli("audit-host", "--root", str(host.root), "--json")
    data = json.loads(out)
    assert {c["id"] for c in data["checks"]} >= {"ssh", "service_user"}
    assert data["baseline_seen"] is False


def test_cli_first_run_says_how_to_get_drift_reporting(tmp_path):
    host = good_host(tmp_path)
    _, out = run_cli("audit-host", "--root", str(host.root))
    assert "--save-baseline" in out


def test_save_baseline_without_state_dir_is_refused(tmp_path):
    host = good_host(tmp_path)
    code, _ = run_cli("audit-host", "--root", str(host.root), "--save-baseline")
    assert code == 2


def test_audit_never_shells_out_when_auditing_a_fake_root(tmp_path, monkeypatch):
    """A --root audit must not read the real host's clock through a command;
    that would mix two hosts' evidence into one baseline."""
    def boom(*a, **k):
        raise AssertionError("subprocess used while auditing a fake root")

    monkeypatch.setattr(ha.subprocess, "run", boom)
    host = ha.Host(root=tmp_path)
    assert ha.check_ntp(host).status == ha.UNKNOWN
