# netmon-sim  —  Network Monitoring Simulator

A Python project that simulates a router-filtered network with a central
monitoring server, CLI interface, and web dashboard.

## Architecture

```
  Subnet A (Clients)         Router (ACL)         Subnet B (Servers)
  192.168.1.0/24  ──────►  policy.yaml  ──────►  192.168.2.0/24
                               │
                               ▼
                        Monitor Server
                     (logs + reports + dashboard)
```

## Quick Start

```bash
# Install
cd netmon-sim
pip install -e ".[dev]"

# Run the simulation
netmon run

# Run with custom config
netmon run --duration 30 --rate 5

# Manage policies live
netmon policy allow dns
netmon policy block ftp
netmon policy reload
netmon policy show

# Generate reports
netmon report --type summary
netmon report --type blocked
netmon report --type unexpected
netmon report --type breakdown

# Launch web dashboard
netmon dashboard

# Run tests
pytest -v
```

## Policy Hot-Reload

Edit `policy.yaml` while the simulation is running — changes are picked up
automatically via filesystem watching (no restart required).

## Web Dashboard

Run `netmon dashboard` and open http://localhost:5050 to see live charts for:

- Traffic volume over time
- Protocol breakdown (pie chart)
- Allowed vs Blocked counts
- Unexpected protocol alerts
