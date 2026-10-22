"""
Packet model and synthetic traffic generator.

Generates realistic network packets across two subnets with a mix of
normal and unexpected traffic (telnet, FTP, unknown ports).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True)
class Packet:
    """Immutable representation of a network packet."""

    src: str
    dst: str
    protocol: str          # "tcp", "udp", "icmp"
    dst_port: int          # 0 for ICMP
    size: int              # bytes
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "src": self.src,
            "dst": self.dst,
            "protocol": self.protocol,
            "dst_port": self.dst_port,
            "size": self.size,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Packet":
        return cls(**d)

    def __str__(self) -> str:
        port_str = f":{self.dst_port}" if self.dst_port else ""
        return (
            f"[{self.protocol.upper():4s}] "
            f"{self.src} → {self.dst}{port_str}  "
            f"({self.size} B)"
        )


# ── Traffic profiles ──────────────────────────────────────────────

# (protocol, dst_port, weight) — weight controls relative frequency
_NORMAL_TRAFFIC = [
    ("tcp",  80,   30),   # HTTP
    ("tcp",  443,  40),   # HTTPS
    ("udp",  53,   15),   # DNS
    ("icmp", 0,    10),   # Ping
]

_UNEXPECTED_TRAFFIC = [
    ("tcp",  23,   2),    # Telnet
    ("tcp",  21,   2),    # FTP
    ("tcp",  9999, 1),    # Unknown port
]

CLIENT_SUBNET = "192.168.1"
SERVER_SUBNET = "192.168.2"


def _random_ip(subnet: str) -> str:
    """Generate a random host IP within a /24 subnet."""
    return f"{subnet}.{random.randint(1, 254)}"


def generate_packet(*, include_unexpected: bool = True) -> Packet:
    """Create a single synthetic packet."""
    profiles = list(_NORMAL_TRAFFIC)
    if include_unexpected:
        profiles.extend(_UNEXPECTED_TRAFFIC)

    protocols, ports, weights = zip(*profiles)
    idx = random.choices(range(len(profiles)), weights=weights, k=1)[0]

    return Packet(
        src=_random_ip(CLIENT_SUBNET),
        dst=_random_ip(SERVER_SUBNET),
        protocol=protocols[idx],
        dst_port=ports[idx],
        size=random.randint(40, 1500),
    )


def generate_stream(
    *,
    rate: float = 10.0,
    duration: float | None = None,
    include_unexpected: bool = True,
) -> Iterator[Packet]:
    """
    Yield packets at approximately *rate* packets/second.

    If *duration* is given (seconds), stop after that many seconds;
    otherwise yield forever.
    """
    start = time.time()
    interval = 1.0 / rate if rate > 0 else 0.1
    while True:
        if duration is not None and (time.time() - start) >= duration:
            break
        yield generate_packet(include_unexpected=include_unexpected)
        time.sleep(interval)


def generate_batch(count: int = 100, *, include_unexpected: bool = True) -> list[Packet]:
    """Return a list of *count* packets instantly (no sleep)."""
    return [generate_packet(include_unexpected=include_unexpected) for _ in range(count)]


# ── Helpers for building specific test packets ────────────────────

def make_packet(
    protocol: str = "tcp",
    dst_port: int = 80,
    src: str | None = None,
    dst: str | None = None,
    size: int = 512,
) -> Packet:
    """Create a packet with explicit parameters (useful in tests)."""
    return Packet(
        src=src or _random_ip(CLIENT_SUBNET),
        dst=dst or _random_ip(SERVER_SUBNET),
        protocol=protocol,
        dst_port=dst_port,
        size=size,
    )
