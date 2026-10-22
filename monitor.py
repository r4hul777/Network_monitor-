"""
Central monitoring server.

Receives every packet decision from the router, stores an in-memory log,
and produces reports: traffic volume, breakdown, unexpected protocols,
allowed-vs-blocked counts — all filterable by time window.
"""

from __future__ import annotations

import time
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Sequence

from netmon_sim.packet import Packet
from netmon_sim.router import Action, Decision


@dataclass
class LogEntry:
    """A single log row stored by the monitor."""

    timestamp: float
    src: str
    dst: str
    protocol: str
    dst_port: int
    size: int
    action: str          # "permit" or "deny"
    rule_description: str

    @classmethod
    def from_decision(cls, d: Decision) -> "LogEntry":
        return cls(
            timestamp=d.packet.timestamp,
            src=d.packet.src,
            dst=d.packet.dst,
            protocol=d.packet.protocol,
            dst_port=d.packet.dst_port,
            size=d.packet.size,
            action=d.action.value,
            rule_description=(
                d.matched_rule.description if d.matched_rule else "implicit deny"
            ),
        )


class Monitor:
    """
    Monitoring server that aggregates packet decisions and produces reports.

    Thread-safe — the simulation can log decisions from one thread while
    the dashboard reads reports from another.
    """

    def __init__(self, whitelist: list[str] | None = None):
        self._lock = threading.Lock()
        self._log: list[LogEntry] = []
        self._whitelist: set[str] = set(whitelist or ["tcp", "udp", "icmp"])

    # ── ingestion ─────────────────────────────────────────

    def record(self, decision: Decision) -> None:
        """Log a single decision."""
        entry = LogEntry.from_decision(decision)
        with self._lock:
            self._log.append(entry)

    def record_batch(self, decisions: Sequence[Decision]) -> None:
        entries = [LogEntry.from_decision(d) for d in decisions]
        with self._lock:
            self._log.extend(entries)

    @property
    def log(self) -> list[LogEntry]:
        with self._lock:
            return list(self._log)

    @property
    def whitelist(self) -> set[str]:
        return set(self._whitelist)

    @whitelist.setter
    def whitelist(self, value: Sequence[str]) -> None:
        self._whitelist = set(v.lower() for v in value)

    # ── filtering ─────────────────────────────────────────

    def _window(
        self, entries: list[LogEntry] | None = None, *, since: float | None = None, until: float | None = None
    ) -> list[LogEntry]:
        """Filter entries by time window."""
        data = entries if entries is not None else self.log
        if since is not None:
            data = [e for e in data if e.timestamp >= since]
        if until is not None:
            data = [e for e in data if e.timestamp <= until]
        return data

    # ── reports ───────────────────────────────────────────

    def report_summary(self, *, since: float | None = None, until: float | None = None) -> dict:
        """Total traffic volume report."""
        entries = self._window(since=since, until=until)
        total_bytes = sum(e.size for e in entries)
        return {
            "total_packets": len(entries),
            "total_bytes": total_bytes,
            "total_kb": round(total_bytes / 1024, 2),
            "window_start": since,
            "window_end": until,
        }

    def report_breakdown(self, *, since: float | None = None, until: float | None = None) -> dict:
        """Packet-type breakdown by protocol and port."""
        entries = self._window(since=since, until=until)
        by_protocol: Counter = Counter()
        by_port: Counter = Counter()
        for e in entries:
            by_protocol[e.protocol] += 1
            by_port[e.dst_port] += 1
        return {
            "by_protocol": dict(by_protocol.most_common()),
            "by_port": dict(by_port.most_common()),
            "total": len(entries),
        }

    def report_unexpected(self, *, since: float | None = None, until: float | None = None) -> dict:
        """Packets whose protocol is NOT in the whitelist."""
        entries = self._window(since=since, until=until)
        unexpected = [e for e in entries if e.protocol.lower() not in self._whitelist]
        return {
            "unexpected_count": len(unexpected),
            "total": len(entries),
            "unexpected_protocols": list({e.protocol for e in unexpected}),
            "entries": [
                {
                    "src": e.src,
                    "dst": e.dst,
                    "protocol": e.protocol,
                    "dst_port": e.dst_port,
                    "action": e.action,
                }
                for e in unexpected
            ],
        }

    def report_allowed_blocked(self, *, since: float | None = None, until: float | None = None) -> dict:
        """Allowed vs. blocked counts."""
        entries = self._window(since=since, until=until)
        allowed = sum(1 for e in entries if e.action == "permit")
        blocked = len(entries) - allowed
        return {
            "allowed": allowed,
            "blocked": blocked,
            "total": len(entries),
            "allowed_pct": round(100 * allowed / len(entries), 1) if entries else 0,
            "blocked_pct": round(100 * blocked / len(entries), 1) if entries else 0,
        }

    def report_blocked_detail(self, *, since: float | None = None, until: float | None = None) -> dict:
        """Detailed list of blocked packets."""
        entries = self._window(since=since, until=until)
        blocked = [e for e in entries if e.action == "deny"]
        by_reason: Counter = Counter()
        for e in blocked:
            by_reason[e.rule_description] += 1
        return {
            "blocked_count": len(blocked),
            "by_reason": dict(by_reason.most_common()),
            "entries": [
                {
                    "src": e.src,
                    "dst": e.dst,
                    "protocol": e.protocol,
                    "dst_port": e.dst_port,
                    "rule": e.rule_description,
                    "timestamp": e.timestamp,
                }
                for e in blocked[-50:]   # last 50
            ],
        }

    def dashboard_data(self) -> dict:
        """Combined data payload for the web dashboard."""
        return {
            "summary": self.report_summary(),
            "breakdown": self.report_breakdown(),
            "unexpected": self.report_unexpected(),
            "allowed_blocked": self.report_allowed_blocked(),
            "recent_log": [
                {
                    "src": e.src,
                    "dst": e.dst,
                    "protocol": e.protocol,
                    "dst_port": e.dst_port,
                    "size": e.size,
                    "action": e.action,
                    "rule": e.rule_description,
                    "timestamp": e.timestamp,
                }
                for e in self.log[-100:]
            ],
        }

    def clear(self) -> None:
        """Reset all logs."""
        with self._lock:
            self._log.clear()
