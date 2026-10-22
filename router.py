"""
Router ACL engine.

Implements an ordered access-control list with Cisco-style wildcard masks,
first-match-wins semantics, and an implicit deny-all at the end.

Supports hot-reload: call ``Router.reload()`` or edit ``policy.yaml``
while the filesystem watcher is running.
"""

from __future__ import annotations

import ipaddress
import struct
import socket
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence

import yaml

from netmon_sim.packet import Packet


class Action(Enum):
    PERMIT = "permit"
    DENY = "deny"


@dataclass
class ACLRule:
    """A single ACL entry."""

    action: Action
    protocol: str              # "tcp", "udp", "icmp", "any"
    src: str                   # e.g. "192.168.1.0"
    src_wildcard: str          # e.g. "0.0.0.255"
    dst: str
    dst_wildcard: str
    dst_port: int              # 0 = any / ICMP
    description: str = ""

    # ── matching helpers ──────────────────────────────────

    @staticmethod
    def _ip_to_int(ip: str) -> int:
        return struct.unpack("!I", socket.inet_aton(ip))[0]

    def _match_ip(self, address: str, rule_ip: str, wildcard: str) -> bool:
        """
        Wildcard-mask match (Cisco-style).
        A wildcard bit of 0 means "must match"; 1 means "don't care".
        """
        addr = self._ip_to_int(address)
        rule = self._ip_to_int(rule_ip)
        wild = self._ip_to_int(wildcard)
        return (addr & ~wild) == (rule & ~wild)

    def matches(self, pkt: Packet) -> bool:
        """Return True if *pkt* matches this rule."""
        # Protocol check
        if self.protocol != "any" and self.protocol != pkt.protocol:
            return False
        # Source IP
        if not self._match_ip(pkt.src, self.src, self.src_wildcard):
            return False
        # Destination IP
        if not self._match_ip(pkt.dst, self.dst, self.dst_wildcard):
            return False
        # Destination port (0 in rule = any)
        if self.dst_port != 0 and self.dst_port != pkt.dst_port:
            return False
        return True


# ── Decision result ───────────────────────────────────────────────

@dataclass
class Decision:
    """Result of the ACL evaluation for one packet."""

    packet: Packet
    action: Action
    matched_rule: ACLRule | None   # None → implicit deny
    rule_index: int | None

    @property
    def is_permitted(self) -> bool:
        return self.action == Action.PERMIT

    def __str__(self) -> str:
        tag = "PERMIT" if self.is_permitted else " DENY "
        rule_desc = (
            self.matched_rule.description
            if self.matched_rule
            else "implicit deny-all"
        )
        return f"[{tag}] {self.packet}  (rule: {rule_desc})"


# ── Router ────────────────────────────────────────────────────────

class Router:
    """
    Ordered ACL engine.

    * First-match-wins
    * Implicit deny at the end
    * Thread-safe hot-reload via ``reload()``
    """

    def __init__(self, policy_path: str | Path = "policy.yaml"):
        self._policy_path = Path(policy_path)
        self._lock = threading.RLock()
        self._rules: list[ACLRule] = []
        self._whitelist: list[str] = []
        self.reload()

    # ── public API ────────────────────────────────────────

    def reload(self) -> None:
        """(Re-)load rules from the YAML policy file."""
        with self._lock:
            data = yaml.safe_load(self._policy_path.read_text())
            self._rules = [self._parse_rule(r) for r in data.get("acl", [])]
            self._whitelist = [p.lower() for p in data.get("whitelist", [])]

    @property
    def rules(self) -> list[ACLRule]:
        with self._lock:
            return list(self._rules)

    @property
    def whitelist(self) -> list[str]:
        with self._lock:
            return list(self._whitelist)

    def evaluate(self, pkt: Packet) -> Decision:
        """
        Evaluate a packet against the ACL.

        Returns a ``Decision`` with the action, matched rule, and rule index.
        """
        with self._lock:
            for idx, rule in enumerate(self._rules):
                if rule.matches(pkt):
                    return Decision(
                        packet=pkt,
                        action=rule.action,
                        matched_rule=rule,
                        rule_index=idx,
                    )
            # implicit deny
            return Decision(
                packet=pkt,
                action=Action.DENY,
                matched_rule=None,
                rule_index=None,
            )

    def evaluate_batch(self, packets: Sequence[Packet]) -> list[Decision]:
        return [self.evaluate(pkt) for pkt in packets]

    # ── policy mutation helpers (used by CLI) ─────────────

    def add_rule(
        self,
        action: str,
        protocol: str,
        dst_port: int,
        *,
        src: str = "0.0.0.0",
        src_wildcard: str = "255.255.255.255",
        dst: str = "0.0.0.0",
        dst_wildcard: str = "255.255.255.255",
        description: str = "",
        position: int = 0,
    ) -> None:
        """Insert a new rule and persist to policy.yaml."""
        rule = ACLRule(
            action=Action(action),
            protocol=protocol,
            src=src,
            src_wildcard=src_wildcard,
            dst=dst,
            dst_wildcard=dst_wildcard,
            dst_port=dst_port,
            description=description,
        )
        with self._lock:
            self._rules.insert(position, rule)
            self._persist()

    def remove_rules_by_port(self, protocol: str, dst_port: int) -> int:
        """Remove all rules matching a given protocol+port. Returns count removed."""
        with self._lock:
            before = len(self._rules)
            self._rules = [
                r
                for r in self._rules
                if not (r.protocol == protocol and r.dst_port == dst_port)
            ]
            removed = before - len(self._rules)
            if removed:
                self._persist()
            return removed

    def apply_preset(self, preset: str) -> None:
        """Apply a named policy preset."""
        preset = preset.lower()
        with self._lock:
            new_rules: list[ACLRule] = []
            if preset == "only_http":
                # User's exact scenario: ONLY HTTP is permitted; everything else blocked
                new_rules.append(ACLRule(
                    action=Action.PERMIT, protocol="tcp",
                    src="192.168.1.0", src_wildcard="0.0.0.255",
                    dst="192.168.2.0", dst_wildcard="0.0.0.255",
                    dst_port=80, description="Allow ONLY HTTP (clients→servers)"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="tcp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=443, description="Block HTTPS (Non-HTTP)"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="udp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=53, description="Block DNS (Non-HTTP)"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="tcp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=23, description="Block Telnet (Non-HTTP)"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="tcp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=21, description="Block FTP (Non-HTTP)"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="icmp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=0, description="Block ICMP Ping (Non-HTTP)"
                ))
            elif preset in ("http_https", "default"):
                new_rules.append(ACLRule(
                    action=Action.PERMIT, protocol="tcp",
                    src="192.168.1.0", src_wildcard="0.0.0.255",
                    dst="192.168.2.0", dst_wildcard="0.0.0.255",
                    dst_port=80, description="Allow HTTP from clients to servers"
                ))
                new_rules.append(ACLRule(
                    action=Action.PERMIT, protocol="tcp",
                    src="192.168.1.0", src_wildcard="0.0.0.255",
                    dst="192.168.2.0", dst_wildcard="0.0.0.255",
                    dst_port=443, description="Allow HTTPS from clients to servers"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="tcp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=23, description="Block Telnet everywhere"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="tcp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=21, description="Block FTP everywhere"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="udp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=53, description="Block DNS"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="icmp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=0, description="Block ICMP ping"
                ))
            elif preset == "allow_dns":
                new_rules.append(ACLRule(
                    action=Action.PERMIT, protocol="tcp",
                    src="192.168.1.0", src_wildcard="0.0.0.255",
                    dst="192.168.2.0", dst_wildcard="0.0.0.255",
                    dst_port=80, description="Allow HTTP from clients to servers"
                ))
                new_rules.append(ACLRule(
                    action=Action.PERMIT, protocol="tcp",
                    src="192.168.1.0", src_wildcard="0.0.0.255",
                    dst="192.168.2.0", dst_wildcard="0.0.0.255",
                    dst_port=443, description="Allow HTTPS from clients to servers"
                ))
                new_rules.append(ACLRule(
                    action=Action.PERMIT, protocol="udp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=53, description="Allow DNS queries"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="tcp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=23, description="Block Telnet everywhere"
                ))
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="tcp",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=21, description="Block FTP everywhere"
                ))
            elif preset == "block_all":
                new_rules.append(ACLRule(
                    action=Action.DENY, protocol="any",
                    src="0.0.0.0", src_wildcard="255.255.255.255",
                    dst="0.0.0.0", dst_wildcard="255.255.255.255",
                    dst_port=0, description="Strict Lockdown - Block All Traffic"
                ))
            self._rules = new_rules
            self._persist()

    def set_service_state(self, service: str, allowed: bool) -> None:
        """Allow or block a specific service by name."""
        svc_map = {
            "http":   ("tcp", 80, "HTTP"),
            "https":  ("tcp", 443, "HTTPS"),
            "dns":    ("udp", 53, "DNS"),
            "ftp":    ("tcp", 21, "FTP"),
            "telnet": ("tcp", 23, "Telnet"),
            "icmp":   ("icmp", 0, "ICMP ping"),
            "ssh":    ("tcp", 22, "SSH"),
        }
        if service not in svc_map:
            return
        proto, port, label = svc_map[service]
        action = Action.PERMIT if allowed else Action.DENY
        desc = f"Allow {label}" if allowed else f"Block {label}"

        with self._lock:
            # Remove existing rule for this proto+port
            self._rules = [r for r in self._rules if not (r.protocol == proto and r.dst_port == port)]
            # Insert at top (first match wins)
            new_rule = ACLRule(
                action=action, protocol=proto,
                src="192.168.1.0" if (allowed and port in (80, 443)) else "0.0.0.0",
                src_wildcard="0.0.0.255" if (allowed and port in (80, 443)) else "255.255.255.255",
                dst="192.168.2.0" if (allowed and port in (80, 443)) else "0.0.0.0",
                dst_wildcard="0.0.0.255" if (allowed and port in (80, 443)) else "255.255.255.255",
                dst_port=port, description=desc,
            )
            self._rules.insert(0, new_rule)
            self._persist()

    # ── internals ─────────────────────────────────────────

    @staticmethod
    def _parse_rule(raw: dict) -> ACLRule:
        return ACLRule(
            action=Action(raw["action"]),
            protocol=raw.get("protocol", "any"),
            src=raw.get("src", "0.0.0.0"),
            src_wildcard=raw.get("src_wildcard", "255.255.255.255"),
            dst=raw.get("dst", "0.0.0.0"),
            dst_wildcard=raw.get("dst_wildcard", "255.255.255.255"),
            dst_port=int(raw.get("dst_port", 0)),
            description=raw.get("description", ""),
        )

    def _persist(self) -> None:
        """Write current rules back to the YAML file."""
        acl_data = []
        for r in self._rules:
            acl_data.append({
                "action": r.action.value,
                "protocol": r.protocol,
                "src": r.src,
                "src_wildcard": r.src_wildcard,
                "dst": r.dst,
                "dst_wildcard": r.dst_wildcard,
                "dst_port": r.dst_port,
                "description": r.description,
            })
        data = {"acl": acl_data, "whitelist": self._whitelist}
        self._policy_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
