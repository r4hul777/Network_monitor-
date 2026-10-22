"""
pytest test suite for netmon-sim.

Tests the five required scenarios:
  1. HTTP allowed
  2. Ping (ICMP) blocked
  3. FTP blocked
  4. Telnet blocked
  5. DNS blocked by default → allowed after a policy change

All tests use a temporary copy of the default policy so they are isolated.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest
import yaml

from netmon_sim.packet import make_packet, Packet
from netmon_sim.router import Router, Action, Decision
from netmon_sim.monitor import Monitor


# ── fixtures ──────────────────────────────────────────────────────

@pytest.fixture()
def policy_file(tmp_path: Path) -> Path:
    """Create a temporary copy of the default policy."""
    src = Path(__file__).parent.parent / "policy.yaml"
    dst = tmp_path / "policy.yaml"
    shutil.copy(src, dst)
    return dst


@pytest.fixture()
def router(policy_file: Path) -> Router:
    return Router(policy_file)


@pytest.fixture()
def monitor() -> Monitor:
    return Monitor()


# ── helpers ───────────────────────────────────────────────────────

def decide(router: Router, **kwargs) -> Decision:
    """Shorthand: create a packet and evaluate it."""
    pkt = make_packet(**kwargs)
    return router.evaluate(pkt)


# ── 1. HTTP is allowed ───────────────────────────────────────────

class TestHTTPAllowed:
    """HTTP (TCP port 80) from client subnet to server subnet should be permitted."""

    def test_http_port_80_permitted(self, router: Router) -> None:
        d = decide(router, protocol="tcp", dst_port=80,
                   src="192.168.1.10", dst="192.168.2.20")
        assert d.is_permitted
        assert d.action == Action.PERMIT

    def test_https_port_443_permitted(self, router: Router) -> None:
        d = decide(router, protocol="tcp", dst_port=443,
                   src="192.168.1.50", dst="192.168.2.100")
        assert d.is_permitted

    def test_http_logged_as_permit(self, router: Router, monitor: Monitor) -> None:
        d = decide(router, protocol="tcp", dst_port=80,
                   src="192.168.1.1", dst="192.168.2.1")
        monitor.record(d)
        report = monitor.report_allowed_blocked()
        assert report["allowed"] == 1
        assert report["blocked"] == 0


# ── 2. Ping (ICMP) is blocked ────────────────────────────────────

class TestPingBlocked:
    """ICMP packets should be denied by the default policy."""

    def test_icmp_denied(self, router: Router) -> None:
        d = decide(router, protocol="icmp", dst_port=0,
                   src="192.168.1.10", dst="192.168.2.10")
        assert not d.is_permitted
        assert d.action == Action.DENY

    def test_icmp_logged_as_blocked(self, router: Router, monitor: Monitor) -> None:
        d = decide(router, protocol="icmp", dst_port=0,
                   src="192.168.1.10", dst="192.168.2.10")
        monitor.record(d)
        report = monitor.report_blocked_detail()
        assert report["blocked_count"] == 1


# ── 3. FTP is blocked ────────────────────────────────────────────

class TestFTPBlocked:
    """FTP (TCP port 21) should be denied."""

    def test_ftp_denied(self, router: Router) -> None:
        d = decide(router, protocol="tcp", dst_port=21,
                   src="192.168.1.10", dst="192.168.2.10")
        assert not d.is_permitted
        assert d.action == Action.DENY

    def test_ftp_from_any_source(self, router: Router) -> None:
        """FTP rule uses wildcard 255.255.255.255 → blocks from anywhere."""
        d = decide(router, protocol="tcp", dst_port=21,
                   src="10.0.0.5", dst="172.16.0.1")
        assert not d.is_permitted


# ── 4. Telnet is blocked ─────────────────────────────────────────

class TestTelnetBlocked:
    """Telnet (TCP port 23) should be denied."""

    def test_telnet_denied(self, router: Router) -> None:
        d = decide(router, protocol="tcp", dst_port=23,
                   src="192.168.1.10", dst="192.168.2.10")
        assert not d.is_permitted
        assert d.action == Action.DENY

    def test_telnet_from_any_source(self, router: Router) -> None:
        d = decide(router, protocol="tcp", dst_port=23,
                   src="10.0.0.99", dst="192.168.2.5")
        assert not d.is_permitted


# ── 5. DNS blocked → allowed after policy change ─────────────────

class TestDNSPolicyChange:
    """
    DNS (UDP port 53) starts blocked.
    After adding a permit rule and reloading, it should be allowed.
    """

    def test_dns_initially_blocked(self, router: Router) -> None:
        d = decide(router, protocol="udp", dst_port=53,
                   src="192.168.1.10", dst="192.168.2.10")
        assert not d.is_permitted
        assert d.action == Action.DENY

    def test_dns_allowed_after_policy_change(self, router: Router, policy_file: Path) -> None:
        # Confirm blocked first
        d1 = decide(router, protocol="udp", dst_port=53,
                    src="192.168.1.10", dst="192.168.2.10")
        assert not d1.is_permitted

        # Modify the policy: remove the deny-DNS rule and add a permit rule
        router.remove_rules_by_port("udp", 53)
        router.add_rule(
            "permit", "udp", 53,
            description="Allow DNS",
            position=0,
        )

        # Now DNS should be permitted
        d2 = decide(router, protocol="udp", dst_port=53,
                    src="192.168.1.10", dst="192.168.2.10")
        assert d2.is_permitted
        assert d2.action == Action.PERMIT

    def test_dns_policy_change_reflected_in_monitor(self, router: Router, monitor: Monitor, policy_file: Path) -> None:
        # Log a blocked DNS packet
        d1 = decide(router, protocol="udp", dst_port=53,
                    src="192.168.1.10", dst="192.168.2.10")
        monitor.record(d1)

        # Change policy
        router.remove_rules_by_port("udp", 53)
        router.add_rule("permit", "udp", 53, description="Allow DNS", position=0)

        # Log an allowed DNS packet
        d2 = decide(router, protocol="udp", dst_port=53,
                    src="192.168.1.10", dst="192.168.2.10")
        monitor.record(d2)

        report = monitor.report_allowed_blocked()
        assert report["allowed"] == 1
        assert report["blocked"] == 1

    def test_dns_hot_reload_from_file(self, router: Router, policy_file: Path) -> None:
        """Simulate hot-reload by editing the YAML file and calling reload()."""
        # DNS is blocked
        d1 = decide(router, protocol="udp", dst_port=53,
                    src="192.168.1.10", dst="192.168.2.10")
        assert not d1.is_permitted

        # Edit the file: add a permit DNS rule at the top
        data = yaml.safe_load(policy_file.read_text())
        data["acl"].insert(0, {
            "action": "permit",
            "protocol": "udp",
            "src": "0.0.0.0",
            "src_wildcard": "255.255.255.255",
            "dst": "0.0.0.0",
            "dst_wildcard": "255.255.255.255",
            "dst_port": 53,
            "description": "Allow DNS (hot-reload test)",
        })
        # Remove the deny DNS rule
        data["acl"] = [
            r for r in data["acl"]
            if not (r.get("protocol") == "udp" and r.get("dst_port") == 53 and r.get("action") == "deny")
        ]
        policy_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

        # Hot-reload
        router.reload()

        # DNS is now allowed
        d2 = decide(router, protocol="udp", dst_port=53,
                    src="192.168.1.10", dst="192.168.2.10")
        assert d2.is_permitted


# ── Additional edge-case tests ───────────────────────────────────

class TestImplicitDeny:
    """Packets that match no rule should be denied (implicit deny-all)."""

    def test_unknown_port_denied(self, router: Router) -> None:
        d = decide(router, protocol="tcp", dst_port=9999,
                   src="192.168.1.10", dst="192.168.2.10")
        assert not d.is_permitted
        assert d.matched_rule is None  # implicit deny

    def test_ssh_denied_by_default(self, router: Router) -> None:
        d = decide(router, protocol="tcp", dst_port=22,
                   src="192.168.1.10", dst="192.168.2.10")
        assert not d.is_permitted


class TestWildcardMasks:
    """Verify that wildcard masks match correctly."""

    def test_http_wrong_subnet_denied(self, router: Router) -> None:
        """HTTP permit rule only allows 192.168.1.x → 192.168.2.x"""
        d = decide(router, protocol="tcp", dst_port=80,
                   src="10.0.0.1", dst="192.168.2.10")
        # The source doesn't match 192.168.1.0/0.0.0.255 → falls through to implicit deny
        assert not d.is_permitted

    def test_ftp_any_any_wildcard(self, router: Router) -> None:
        """FTP deny uses 255.255.255.255 wildcard → matches any IP."""
        d = decide(router, protocol="tcp", dst_port=21,
                   src="172.16.5.5", dst="10.10.10.10")
        assert not d.is_permitted


class TestMonitorReports:
    """Verify the monitor produces correct report data."""

    def test_breakdown_report(self, router: Router, monitor: Monitor) -> None:
        pkts = [
            make_packet(protocol="tcp", dst_port=80, src="192.168.1.1", dst="192.168.2.1"),
            make_packet(protocol="tcp", dst_port=80, src="192.168.1.2", dst="192.168.2.2"),
            make_packet(protocol="icmp", dst_port=0, src="192.168.1.3", dst="192.168.2.3"),
        ]
        for pkt in pkts:
            monitor.record(router.evaluate(pkt))

        bd = monitor.report_breakdown()
        assert bd["by_protocol"]["tcp"] == 2
        assert bd["by_protocol"]["icmp"] == 1
        assert bd["total"] == 3

    def test_unexpected_protocol_report(self, monitor: Monitor, router: Router) -> None:
        """With whitelist = [tcp, udp, icmp], nothing is unexpected for default traffic."""
        pkt = make_packet(protocol="tcp", dst_port=80, src="192.168.1.1", dst="192.168.2.1")
        monitor.record(router.evaluate(pkt))
        report = monitor.report_unexpected()
        assert report["unexpected_count"] == 0

    def test_summary_volume(self, router: Router, monitor: Monitor) -> None:
        pkt = make_packet(protocol="tcp", dst_port=80, src="192.168.1.1", dst="192.168.2.1", size=1000)
        monitor.record(router.evaluate(pkt))
        summary = monitor.report_summary()
        assert summary["total_packets"] == 1
        assert summary["total_bytes"] == 1000
