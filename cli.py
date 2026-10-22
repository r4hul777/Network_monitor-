"""
CLI interface for netmon-sim.

Commands:
  netmon run          — Run the simulation
  netmon policy ...   — Manage ACL rules
  netmon report ...   — Generate reports
  netmon dashboard    — Launch the web dashboard
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from netmon_sim.router import Router, Action
from netmon_sim.monitor import Monitor
from netmon_sim.simulation import Simulation

console = Console()

# Well-known service → (protocol, port) mapping for shorthand names
_SERVICES = {
    "http":   ("tcp", 80),
    "https":  ("tcp", 443),
    "dns":    ("udp", 53),
    "ftp":    ("tcp", 21),
    "telnet": ("tcp", 23),
    "ssh":    ("tcp", 22),
    "smtp":   ("tcp", 25),
    "ping":   ("icmp", 0),
    "icmp":   ("icmp", 0),
}


def _resolve_service(service: str) -> tuple[str, int]:
    """Resolve a service name or protocol:port string."""
    service = service.lower().strip()
    if service in _SERVICES:
        return _SERVICES[service]
    if ":" in service:
        proto, port = service.split(":", 1)
        return proto, int(port)
    raise click.BadParameter(
        f"Unknown service '{service}'. Use a name ({', '.join(_SERVICES)}) or proto:port."
    )


def _find_policy() -> Path:
    """Locate policy.yaml — check CWD first, then package dir."""
    for candidate in [Path("policy.yaml"), Path(__file__).parent.parent / "policy.yaml"]:
        if candidate.exists():
            return candidate.resolve()
    # Create a default one in CWD
    default = Path("policy.yaml")
    console.print("[yellow]No policy.yaml found — creating default in CWD[/yellow]")
    import shutil
    src = Path(__file__).parent.parent / "policy.yaml"
    if src.exists():
        shutil.copy(src, default)
    return default.resolve()


# ── CLI group ─────────────────────────────────────────────────────

@click.group()
@click.option("--policy", default=None, type=click.Path(), help="Path to policy.yaml")
@click.pass_context
def cli(ctx: click.Context, policy: str | None) -> None:
    """netmon-sim — Network Monitoring Simulator"""
    ctx.ensure_object(dict)
    ctx.obj["policy_path"] = Path(policy) if policy else _find_policy()


# ── netmon run ────────────────────────────────────────────────────

@cli.command()
@click.option("--duration", "-d", default=30.0, help="Simulation duration in seconds")
@click.option("--rate", "-r", default=5.0, help="Packets per second")
@click.option("--no-unexpected", is_flag=True, help="Disable unexpected traffic")
@click.pass_context
def run(ctx: click.Context, duration: float, rate: float, no_unexpected: bool) -> None:
    """Run the network simulation."""
    policy_path = ctx.obj["policy_path"]
    console.print(Panel(
        f"[bold cyan]netmon-sim[/bold cyan] — Simulation\n"
        f"Policy:   {policy_path}\n"
        f"Duration: {duration}s  |  Rate: {rate} pkt/s\n"
        f"Unexpected traffic: {'[red]off[/red]' if no_unexpected else '[green]on[/green]'}",
        title="🌐 Starting",
        border_style="cyan",
    ))

    def on_decision(d):
        colour = "green" if d.is_permitted else "red"
        console.print(f"  [{colour}]{d}[/{colour}]")

    def on_reload():
        console.print("  [yellow]⟳  Policy reloaded![/yellow]")

    sim = Simulation(
        policy_path,
        rate=rate,
        duration=duration,
        include_unexpected=not no_unexpected,
        on_decision=on_decision,
        on_reload=on_reload,
    )

    try:
        sim.start()
    except KeyboardInterrupt:
        sim.stop()

    # Print final summary
    console.print()
    _print_summary(sim.monitor)


def _print_summary(monitor: Monitor) -> None:
    """Print a rich summary table."""
    summary = monitor.report_summary()
    ab = monitor.report_allowed_blocked()
    breakdown = monitor.report_breakdown()

    table = Table(title="📊 Simulation Summary", box=box.ROUNDED, border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total packets", str(summary["total_packets"]))
    table.add_row("Total volume", f"{summary['total_kb']} KB")
    table.add_row("Allowed", f"[green]{ab['allowed']}[/green] ({ab['allowed_pct']}%)")
    table.add_row("Blocked", f"[red]{ab['blocked']}[/red] ({ab['blocked_pct']}%)")

    for proto, count in breakdown["by_protocol"].items():
        table.add_row(f"  {proto.upper()}", str(count))

    console.print(table)


# ── netmon policy ─────────────────────────────────────────────────

@cli.group()
@click.pass_context
def policy(ctx: click.Context) -> None:
    """Manage ACL policy rules."""
    pass


@policy.command("show")
@click.pass_context
def policy_show(ctx: click.Context) -> None:
    """Display current ACL rules."""
    router = Router(ctx.obj["policy_path"])
    table = Table(title="📋 ACL Rules", box=box.ROUNDED, border_style="cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Action", width=8)
    table.add_column("Proto", width=6)
    table.add_column("Src", width=20)
    table.add_column("Dst", width=20)
    table.add_column("Port", width=6, justify="right")
    table.add_column("Description")

    for i, rule in enumerate(router.rules):
        colour = "green" if rule.action == Action.PERMIT else "red"
        table.add_row(
            str(i),
            f"[{colour}]{rule.action.value}[/{colour}]",
            rule.protocol,
            f"{rule.src}/{rule.src_wildcard}",
            f"{rule.dst}/{rule.dst_wildcard}",
            str(rule.dst_port),
            rule.description,
        )

    table.add_row("*", "[red]deny[/red]", "any", "any", "any", "*", "[dim]implicit deny-all[/dim]")
    console.print(table)


@policy.command("allow")
@click.argument("service")
@click.pass_context
def policy_allow(ctx: click.Context, service: str) -> None:
    """Add a PERMIT rule for a service (e.g. dns, http, tcp:8080)."""
    proto, port = _resolve_service(service)
    router = Router(ctx.obj["policy_path"])

    # Remove any existing deny rules for this service first
    removed = router.remove_rules_by_port(proto, port)

    router.add_rule(
        "permit",
        proto,
        port,
        description=f"Allow {service.upper()}",
        position=0,   # insert at the top so it wins
    )
    console.print(f"[green]✓[/green] Added PERMIT rule for {service.upper()} ({proto}:{port})")
    if removed:
        console.print(f"  [dim]Removed {removed} previous rule(s) for {proto}:{port}[/dim]")


@policy.command("block")
@click.argument("service")
@click.pass_context
def policy_block(ctx: click.Context, service: str) -> None:
    """Add a DENY rule for a service."""
    proto, port = _resolve_service(service)
    router = Router(ctx.obj["policy_path"])

    # Remove any existing permit rules for this service first
    removed = router.remove_rules_by_port(proto, port)

    router.add_rule(
        "deny",
        proto,
        port,
        description=f"Block {service.upper()}",
        position=0,
    )
    console.print(f"[red]✗[/red] Added DENY rule for {service.upper()} ({proto}:{port})")
    if removed:
        console.print(f"  [dim]Removed {removed} previous rule(s) for {proto}:{port}[/dim]")


@policy.command("reload")
@click.pass_context
def policy_reload(ctx: click.Context) -> None:
    """Force-reload policy from disk."""
    router = Router(ctx.obj["policy_path"])
    console.print("[green]✓[/green] Policy reloaded from disk.")


# ── netmon report ─────────────────────────────────────────────────

@cli.command()
@click.option("--type", "-t", "report_type", default="summary",
              type=click.Choice(["summary", "breakdown", "unexpected", "blocked", "allowed"]),
              help="Report type")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def report(ctx: click.Context, report_type: str, as_json: bool) -> None:
    """Generate a report (runs a quick batch simulation first)."""
    policy_path = ctx.obj["policy_path"]
    sim = Simulation(policy_path, include_unexpected=True)
    sim.process_batch(200)

    report_map = {
        "summary": sim.monitor.report_summary,
        "breakdown": sim.monitor.report_breakdown,
        "unexpected": sim.monitor.report_unexpected,
        "blocked": sim.monitor.report_blocked_detail,
        "allowed": sim.monitor.report_allowed_blocked,
    }

    data = report_map[report_type]()

    if as_json:
        console.print_json(json.dumps(data, default=str))
        return

    # Rich-formatted output
    if report_type == "summary":
        table = Table(title="📊 Traffic Summary", box=box.ROUNDED, border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_row("Total packets", str(data["total_packets"]))
        table.add_row("Total volume", f"{data['total_kb']} KB")
        console.print(table)

    elif report_type == "breakdown":
        table = Table(title="📊 Protocol Breakdown", box=box.ROUNDED, border_style="cyan")
        table.add_column("Protocol", style="bold")
        table.add_column("Count", justify="right")
        for proto, count in data["by_protocol"].items():
            table.add_row(proto.upper(), str(count))
        console.print(table)

        table2 = Table(title="📊 Port Breakdown", box=box.ROUNDED, border_style="cyan")
        table2.add_column("Port", style="bold")
        table2.add_column("Count", justify="right")
        for port, count in data["by_port"].items():
            table2.add_row(str(port), str(count))
        console.print(table2)

    elif report_type == "unexpected":
        console.print(f"[bold]Unexpected protocols:[/bold] {data['unexpected_count']} / {data['total']}")
        if data["unexpected_protocols"]:
            for p in data["unexpected_protocols"]:
                console.print(f"  [red]• {p}[/red]")
        else:
            console.print("  [green]None — all traffic uses whitelisted protocols.[/green]")

    elif report_type == "blocked":
        console.print(f"[bold red]Blocked packets:[/bold red] {data['blocked_count']}")
        if data["by_reason"]:
            table = Table(title="Block Reasons", box=box.SIMPLE)
            table.add_column("Rule")
            table.add_column("Count", justify="right")
            for reason, count in data["by_reason"].items():
                table.add_row(reason, str(count))
            console.print(table)

    elif report_type == "allowed":
        console.print(f"[green]Allowed:[/green] {data['allowed']} ({data['allowed_pct']}%)")
        console.print(f"[red]Blocked:[/red] {data['blocked']} ({data['blocked_pct']}%)")


# ── netmon dashboard ──────────────────────────────────────────────

@cli.command()
@click.option("--port", "-p", default=5050, help="Dashboard port")
@click.option("--rate", "-r", default=3.0, help="Simulation packets/second")
@click.pass_context
def dashboard(ctx: click.Context, port: int, rate: float) -> None:
    """Launch the web dashboard with live simulation."""
    from netmon_sim.dashboard import create_app

    policy_path = ctx.obj["policy_path"]
    sim = Simulation(policy_path, rate=rate, include_unexpected=True)
    sim_thread = sim.start_background()

    app = create_app(sim)
    console.print(Panel(
        f"[bold cyan]Dashboard[/bold cyan] running at http://localhost:{port}\n"
        f"Simulation rate: {rate} pkt/s  |  Policy: {policy_path}",
        title="🖥  Web Dashboard",
        border_style="cyan",
    ))

    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        sim.stop()


if __name__ == "__main__":
    cli()
