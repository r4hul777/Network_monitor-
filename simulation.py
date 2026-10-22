"""
Simulation engine.

Ties together the packet generator, router, and monitor.
Supports filesystem-based hot-reload of the policy file.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from netmon_sim.packet import generate_packet, generate_batch
from netmon_sim.router import Router
from netmon_sim.monitor import Monitor


class _PolicyReloader(FileSystemEventHandler):
    """Watchdog handler that reloads the router on policy file changes."""

    def __init__(self, router: Router, policy_path: Path, on_reload: Callable | None = None):
        super().__init__()
        self._router = router
        self._policy_file = policy_path.name
        self._on_reload = on_reload

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        if Path(event.src_path).name == self._policy_file:
            try:
                self._router.reload()
                if self._on_reload:
                    self._on_reload()
            except Exception as exc:
                # Don't crash the watcher on a bad YAML edit
                pass


class Simulation:
    """
    Run the full simulation loop.

    Creates packets → pushes through the router → logs decisions to the
    monitor.  Optionally watches for policy-file changes and hot-reloads.
    """

    def __init__(
        self,
        policy_path: str | Path = "policy.yaml",
        *,
        rate: float = 10.0,
        duration: float | None = None,
        include_unexpected: bool = True,
        on_decision: Callable | None = None,
        on_reload: Callable | None = None,
    ):
        self.policy_path = Path(policy_path)
        self.router = Router(self.policy_path)
        self.monitor = Monitor(whitelist=self.router.whitelist)
        self.rate = rate
        self.duration = duration
        self.include_unexpected = include_unexpected
        self._on_decision = on_decision
        self._on_reload = on_reload
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._observer: Observer | None = None

    # ── lifecycle ─────────────────────────────────────────

    def start(self) -> None:
        """Start the simulation (blocking)."""
        self._start_watcher()
        try:
            self._run_loop()
        finally:
            self._stop_watcher()

    def start_background(self) -> threading.Thread:
        """Start simulation in a daemon thread. Returns the thread."""
        t = threading.Thread(target=self.start, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        """Signal the simulation to stop."""
        self._stop.set()

    def pause(self) -> None:
        """Pause auto-generation of packets."""
        self._paused.set()

    def resume(self) -> None:
        """Resume auto-generation of packets."""
        self._paused.clear()

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

    # ── internals ─────────────────────────────────────────

    def _run_loop(self) -> None:
        interval = 1.0 / self.rate if self.rate > 0 else 0.1
        start_time = time.time()

        while not self._stop.is_set():
            if self._paused.is_set():
                self._stop.wait(0.2)
                continue

            if self.duration and (time.time() - start_time) >= self.duration:
                break

            pkt = generate_packet(include_unexpected=self.include_unexpected)
            decision = self.router.evaluate(pkt)
            self.monitor.record(decision)

            if self._on_decision:
                self._on_decision(decision)

            self._stop.wait(interval)

    def _start_watcher(self) -> None:
        """Start watching the policy file for changes."""
        handler = _PolicyReloader(
            self.router,
            self.policy_path,
            on_reload=self._on_reload,
        )
        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(self.policy_path.parent),
            recursive=False,
        )
        self._observer.daemon = True
        self._observer.start()

    def _stop_watcher(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)

    def process_packet(self, pkt: Packet):
        """Process a single packet through the router and log it to monitor."""
        decision = self.router.evaluate(pkt)
        self.monitor.record(decision)
        if self._on_decision:
            self._on_decision(decision)
        return decision

    def process_batch(self, count: int = 100) -> None:
        """Generate and process a batch of packets instantly (for tests)."""
        packets = generate_batch(count, include_unexpected=self.include_unexpected)
        decisions = self.router.evaluate_batch(packets)
        self.monitor.record_batch(decisions)
