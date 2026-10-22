"""
Flask web dashboard for Network Monitor.

Enhanced with React Bits inspired components: SpotlightCard, Animated Squares/Grid,
ShinyText, Animated CountUp, BorderTrail, Gliding Tabs, and DecryptedText.
"""

from __future__ import annotations

import json
from flask import Flask, jsonify, render_template_string, request

from netmon_sim.simulation import Simulation
from netmon_sim.packet import Packet

# ── HTML template ─────────────────────────────────────────────────

_DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Monitor — Real-time Dashboard & Packet Lab</title>
    <meta name="description" content="Enterprise Network Monitor with Router ACL Filtering, Manual Packet Inspection Lab, and Real-Time Telemetry">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-primary:   #080c14;
            --bg-card:      #0d1424;
            --bg-card-alt:  #121b30;
            --border:       #1e293b;
            --border-hover: #334155;
            --text-primary: #f8fafc;
            --text-dim:     #94a3b8;
            --text-muted:   #64748b;
            --accent-cyan:  #06b6d4;
            --accent-blue:  #3b82f6;
            --accent-purple:#8b5cf6;
            --accent-green: #10b981;
            --accent-red:   #ef4444;
            --accent-amber: #f59e0b;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }

        /* ── ReactBits: Animated Canvas Background (Squares) ─────────── */
        #bg-canvas {
            position: fixed;
            inset: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
            opacity: 0.6;
        }

        /* ── Header ───────────────────────────────────── */
        .header {
            position: sticky;
            top: 0;
            z-index: 50;
            padding: 0.85rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            backdrop-filter: blur(20px);
            background: rgba(8, 12, 20, 0.85);
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }

        .header-logo {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #060a14;
            font-weight: 800;
            font-size: 0.82rem;
            letter-spacing: -0.5px;
            box-shadow: 0 0 15px rgba(6, 182, 212, 0.3);
        }

        /* ReactBits: ShinyText */
        .shiny-title {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.3px;
            background: linear-gradient(120deg, #94a3b8 0%, #ffffff 50%, #94a3b8 100%);
            background-size: 200% 100%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: shinySweep 6s ease-in-out infinite;
        }

        @keyframes shinySweep {
            0%, 100% { background-position: 200% 0; }
            50%      { background-position: -200% 0; }
        }

        .header-title p {
            font-size: 0.72rem;
            color: var(--text-muted);
            letter-spacing: 0.02em;
        }

        /* ReactBits: Gliding Pill Tabs */
        .tabs-wrapper {
            position: relative;
            display: flex;
            background: rgba(13, 20, 36, 0.9);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 3px;
        }

        .tab-glider {
            position: absolute;
            top: 3px;
            bottom: 3px;
            border-radius: 6px;
            background: #1e293b;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
            z-index: 1;
        }

        .nav-tab {
            position: relative;
            z-index: 2;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-dim);
            cursor: pointer;
            transition: color 0.15s ease;
            background: transparent;
            border: none;
        }

        .nav-tab:hover {
            color: var(--text-primary);
        }

        .nav-tab.active {
            color: var(--text-primary);
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        /* ReactBits: Magnet Button micro-interaction */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 6px 14px;
            border-radius: 7px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text-primary);
            user-select: none;
        }

        .btn:hover {
            border-color: var(--border-hover);
            background: var(--bg-card-alt);
            transform: translateY(-1px);
        }

        .btn-primary {
            background: var(--accent-cyan);
            color: #041019;
            border: 1px solid var(--accent-cyan);
            font-weight: 600;
        }

        .btn-primary:hover {
            background: #22d3ee;
            border-color: #22d3ee;
            box-shadow: 0 0 15px rgba(6, 182, 212, 0.3);
            transform: translateY(-1px);
        }

        .btn-danger {
            border-color: rgba(239, 68, 68, 0.3);
            color: var(--accent-red);
        }

        .btn-danger:hover {
            background: rgba(239, 68, 68, 0.1);
            border-color: var(--accent-red);
        }

        .status-dot {
            width: 7px; height: 7px;
            border-radius: 50%;
            background: var(--accent-green);
            transition: all 0.2s ease;
        }

        .status-dot.active {
            box-shadow: 0 0 8px rgba(16, 185, 129, 0.8);
        }

        .status-dot.paused {
            background: var(--accent-amber);
            box-shadow: 0 0 8px rgba(245, 158, 11, 0.8);
        }

        /* ── Container ───────────────────────────────── */
        .container {
            position: relative;
            z-index: 1;
            max-width: 1440px;
            margin: 0 auto;
            padding: 1.5rem 2rem;
        }

        .view-section {
            display: none;
            animation: fadeInView 0.25s ease;
        }

        @keyframes fadeInView {
            from { opacity: 0; transform: translateY(4px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .view-section.active {
            display: block;
        }

        /* ── ReactBits: SpotlightCard Component ──────────────────────── */
        .spotlight-card {
            position: relative;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .spotlight-card::before {
            content: '';
            position: absolute;
            inset: 0;
            background: radial-gradient(
                450px circle at var(--mouse-x, -500px) var(--mouse-y, -500px),
                rgba(6, 182, 212, 0.1),
                transparent 70%
            );
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s ease;
            z-index: 1;
        }

        .spotlight-card:hover {
            border-color: var(--border-hover);
        }

        .spotlight-card:hover::before {
            opacity: 1;
        }

        .spotlight-content {
            position: relative;
            z-index: 2;
        }

        /* ── Stat cards ──────────────────────────────── */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.25rem;
            margin-bottom: 1.25rem;
        }

        .stat-card-inner {
            padding: 1.25rem 1.5rem;
        }

        .stat-label {
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            margin-bottom: 0.45rem;
        }

        .stat-value {
            font-size: 1.85rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            font-variant-numeric: tabular-nums;
        }

        .stat-sub {
            font-size: 0.78rem;
            color: var(--text-dim);
            margin-top: 0.3rem;
        }

        /* ── Charts Grid ─────────────────────────────── */
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.25rem;
            margin-bottom: 1.25rem;
        }

        .panel-inner {
            padding: 1.25rem 1.5rem;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .panel-title {
            font-size: 0.88rem;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: -0.2px;
        }

        .chart-box {
            position: relative;
            width: 100%;
            height: 250px;
        }

        /* ── Quick Policy Bar ────────────────────────── */
        .quick-bar {
            padding: 0.85rem 1.25rem;
            margin-bottom: 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.75rem;
        }

        .quick-bar-left {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.82rem;
        }

        .quick-label {
            color: var(--text-muted);
            font-weight: 600;
            margin-right: 0.25rem;
        }

        .preset-btn {
            padding: 5px 11px;
            border-radius: 6px;
            font-size: 0.76rem;
            font-weight: 600;
            background: #141f38;
            border: 1px solid var(--border);
            color: var(--text-dim);
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .preset-btn:hover {
            border-color: var(--accent-cyan);
            color: var(--text-primary);
        }

        .preset-btn.highlight {
            background: rgba(6, 182, 212, 0.12);
            border-color: var(--accent-cyan);
            color: var(--accent-cyan);
            box-shadow: 0 0 10px rgba(6, 182, 212, 0.2);
        }

        /* ── Manual Lab Panel ────────────────────────── */
        .lab-panel-inner {
            padding: 1.5rem;
            margin-bottom: 1.25rem;
        }

        .lab-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1.25rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1rem;
        }

        .lab-badge {
            display: inline-block;
            padding: 2px 8px;
            background: rgba(6, 182, 212, 0.1);
            color: var(--accent-cyan);
            border: 1px solid rgba(6, 182, 212, 0.25);
            border-radius: 5px;
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.35rem;
        }

        .preset-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 1.25rem;
            align-items: center;
        }

        .service-toggles {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-bottom: 1.25rem;
            padding: 0.75rem 1rem;
            background: #090d16;
            border: 1px solid var(--border);
            border-radius: 8px;
            align-items: center;
        }

        .svc-chip {
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.74rem;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.15s ease;
        }

        .svc-chip.allowed {
            background: rgba(16, 185, 129, 0.12);
            color: var(--accent-green);
            border-color: rgba(16, 185, 129, 0.25);
        }

        .svc-chip.blocked {
            background: rgba(239, 68, 68, 0.1);
            color: var(--accent-red);
            border-color: rgba(239, 68, 68, 0.2);
        }

        /* ── Injector Form ───────────────────────────── */
        .injector-card {
            background: #090d16;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.25rem;
            margin-bottom: 1.25rem;
        }

        .injector-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr) auto;
            gap: 0.75rem;
            align-items: flex-end;
            margin-top: 0.85rem;
            margin-bottom: 1rem;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }

        .form-label {
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .form-input, .form-select {
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 7px;
            padding: 8px 10px;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            outline: none;
            transition: border-color 0.15s ease;
        }

        .form-input:focus, .form-select:focus {
            border-color: var(--accent-cyan);
        }

        /* ── ReactBits: BorderTrail on Decision Result Card ───────────────── */
        .decision-result {
            position: relative;
            padding: 1rem 1.25rem;
            border-radius: 8px;
            background: #0f172a;
            border: 1px solid var(--border);
            display: none;
            overflow: hidden;
            animation: fadeIn 0.25s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-4px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .decision-result.show {
            display: block;
        }

        /* Border Trail light beam */
        .border-trail {
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
            animation: borderTrailMove 2s linear infinite;
        }

        @keyframes borderTrailMove {
            0%   { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .decision-banner {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin-bottom: 0.45rem;
        }

        .decision-badge {
            font-size: 0.78rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 5px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .decision-badge.permit {
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .decision-badge.deny {
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .decision-detail {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            color: var(--text-dim);
            line-height: 1.5;
        }

        /* ── ReactBits: Animated List & Activity Feed ────────────────────── */
        .log-container {
            position: relative;
            max-height: 380px;
            overflow-y: auto;
            mask-image: linear-gradient(to bottom, black 85%, transparent 100%);
            -webkit-mask-image: linear-gradient(to bottom, black 85%, transparent 100%);
        }

        .log-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.76rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .log-table th {
            text-align: left;
            padding: 0.6rem 0.75rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.68rem;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            background: var(--bg-card);
            z-index: 10;
        }

        .log-table td {
            padding: 0.45rem 0.75rem;
            border-bottom: 1px solid rgba(30, 41, 59, 0.6);
        }

        .log-row-enter {
            animation: rowEntrance 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes rowEntrance {
            from {
                opacity: 0;
                transform: translateY(-4px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .log-table tr:hover {
            background: rgba(255, 255, 255, 0.02);
        }

        .badge {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 5px;
            font-size: 0.68rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-permit {
            background: rgba(16, 185, 129, 0.12);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.25);
        }

        .badge-deny {
            background: rgba(239, 68, 68, 0.12);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.25);
        }

        .badge-proto {
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent-blue);
            border: 1px solid rgba(59, 130, 246, 0.2);
        }

        .badge-port {
            background: rgba(139, 92, 246, 0.1);
            color: var(--accent-purple);
            border: 1px solid rgba(139, 92, 246, 0.2);
        }

        /* ── About Section ────────────────────────────── */
        .about-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.25rem;
            margin-bottom: 1.25rem;
        }

        .about-card-inner {
            padding: 1.5rem;
        }

        .about-card h3 {
            font-size: 0.98rem;
            font-weight: 700;
            color: var(--accent-cyan);
            margin-bottom: 0.75rem;
            letter-spacing: -0.2px;
        }

        .about-card p, .about-card li {
            font-size: 0.84rem;
            color: var(--text-dim);
            line-height: 1.6;
        }

        .about-card ul {
            margin-left: 1.25rem;
            margin-top: 0.5rem;
        }

        .topo-box {
            background: #090d16;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            line-height: 1.5;
            color: var(--text-primary);
        }

        @media (max-width: 1024px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .charts-grid { grid-template-columns: 1fr; }
            .about-grid { grid-template-columns: 1fr; }
            .injector-grid { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <!-- ReactBits: Squares Background Canvas -->
    <canvas id="bg-canvas"></canvas>

    <!-- ── Header ──────────────────────────────────────── -->
    <header class="header">
        <div class="header-brand">
            <div class="header-logo">NM</div>
            <div class="header-title">
                <h1 class="shiny-title">Network Monitor</h1>
                <p>Router ACL Filtering & Real-Time Traffic Telemetry</p>
            </div>
        </div>

        <!-- ReactBits: Sliding Glider Tabs -->
        <nav class="tabs-wrapper" id="navTabs">
            <div class="tab-glider" id="tabGlider"></div>
            <button class="nav-tab active" onclick="switchView('dashboard', this)">Live Dashboard</button>
            <button class="nav-tab" onclick="switchView('lab', this)">Manual Packet Lab</button>
            <button class="nav-tab" onclick="switchView('about', this)">About Project</button>
        </nav>

        <div class="header-actions">
            <button id="btnPause" class="btn" onclick="toggleSim()">
                <span class="status-dot active" id="simDot"></span>
                <span id="simText">Stream: Active</span>
            </button>
            <button class="btn btn-danger" onclick="clearLogs()">Clear</button>
        </div>
    </header>

    <main class="container">
        <!-- ── TAB 1: Live Dashboard ───────────────────── -->
        <section id="view-dashboard" class="view-section active">
            <!-- Stats with ReactBits SpotlightCard & CountUp -->
            <div class="stats-grid">
                <div class="spotlight-card">
                    <div class="spotlight-content stat-card-inner">
                        <div class="stat-label">Total Traffic</div>
                        <div class="stat-value" id="stat-packets" data-target="0">0</div>
                        <div class="stat-sub" id="stat-volume">0 KB transferred</div>
                    </div>
                </div>
                <div class="spotlight-card">
                    <div class="spotlight-content stat-card-inner">
                        <div class="stat-label">Permitted</div>
                        <div class="stat-value" style="color: var(--accent-green)" id="stat-allowed" data-target="0">0</div>
                        <div class="stat-sub" id="stat-allowed-pct">0% pass rate</div>
                    </div>
                </div>
                <div class="spotlight-card">
                    <div class="spotlight-content stat-card-inner">
                        <div class="stat-label">Identified & Blocked</div>
                        <div class="stat-value" style="color: var(--accent-red)" id="stat-blocked" data-target="0">0</div>
                        <div class="stat-sub" id="stat-blocked-pct">0% drop rate</div>
                    </div>
                </div>
                <div class="spotlight-card">
                    <div class="spotlight-content stat-card-inner">
                        <div class="stat-label">Foreign / Unexpected</div>
                        <div class="stat-value" style="color: var(--accent-amber)" id="stat-unexpected" data-target="0">0</div>
                        <div class="stat-sub" id="stat-unexpected-sub">Probes / Foreign ports</div>
                    </div>
                </div>
            </div>

            <!-- Quick policy bar -->
            <div class="spotlight-card" style="margin-bottom: 1.25rem;">
                <div class="spotlight-content quick-bar">
                    <div class="quick-bar-left">
                        <span class="quick-label">Policy Mode:</span>
                        <button class="preset-btn highlight" id="qp-only-http" onclick="applyPreset('only_http')">Allow ONLY HTTP</button>
                        <button class="preset-btn" id="qp-http-https" onclick="applyPreset('http_https')">Allow HTTP + HTTPS</button>
                        <button class="preset-btn" id="qp-allow-dns" onclick="applyPreset('allow_dns')">Allow DNS</button>
                        <button class="preset-btn" id="qp-block-all" onclick="applyPreset('block_all')">Lockdown</button>
                        <button class="preset-btn" id="qp-default" onclick="applyPreset('default')">Reset Default</button>
                    </div>
                    <button class="btn btn-primary" onclick="switchViewByName('lab')">Open Packet Lab &rarr;</button>
                </div>
            </div>

            <!-- Charts in SpotlightCards -->
            <div class="charts-grid">
                <div class="spotlight-card">
                    <div class="spotlight-content panel-inner">
                        <div class="panel-header">
                            <div class="panel-title">Protocol Distribution</div>
                        </div>
                        <div class="chart-box"><canvas id="chart-protocol"></canvas></div>
                    </div>
                </div>
                <div class="spotlight-card">
                    <div class="spotlight-content panel-inner">
                        <div class="panel-header">
                            <div class="panel-title">Allowed vs. Blocked Ratio</div>
                        </div>
                        <div class="chart-box"><canvas id="chart-action"></canvas></div>
                    </div>
                </div>
                <div class="spotlight-card">
                    <div class="spotlight-content panel-inner">
                        <div class="panel-header">
                            <div class="panel-title">Traffic by Port / Service</div>
                        </div>
                        <div class="chart-box"><canvas id="chart-ports"></canvas></div>
                    </div>
                </div>
                <div class="spotlight-card">
                    <div class="spotlight-content panel-inner">
                        <div class="panel-header">
                            <div class="panel-title">Real-Time Traffic Timeline</div>
                        </div>
                        <div class="chart-box"><canvas id="chart-timeline"></canvas></div>
                    </div>
                </div>
            </div>

            <!-- ReactBits: Animated List Activity Log -->
            <div class="spotlight-card">
                <div class="spotlight-content panel-inner">
                    <div class="panel-header">
                        <div class="panel-title">Recent Packet Telemetry</div>
                        <span style="font-size: 0.75rem; color: var(--text-dim);" id="logCount">Showing recent packets</span>
                    </div>
                    <div class="log-container">
                        <table class="log-table">
                            <thead>
                                <tr>
                                    <th>Action</th>
                                    <th>Protocol</th>
                                    <th>Source IP</th>
                                    <th>Destination IP</th>
                                    <th>Port / Service</th>
                                    <th>Size</th>
                                    <th>Enforced Rule / Inspection Reason</th>
                                </tr>
                            </thead>
                            <tbody id="log-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- ── TAB 2: Manual Packet Lab ────────────────── -->
        <section id="view-lab" class="view-section">
            <div class="spotlight-card" style="margin-bottom: 1.25rem;">
                <div class="spotlight-content lab-panel-inner">
                    <div class="lab-header">
                        <div>
                            <span class="lab-badge">Interactive Firewall Console</span>
                            <h2 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.35rem;">Manual Packet Injection & Policy Testing</h2>
                            <p style="font-size: 0.82rem; color: var(--text-dim);">
                                Set custom firewall rules (e.g. <b>Allow ONLY HTTP</b>) and inject test packets to inspect identification and blocking behavior in real time.
                            </p>
                        </div>
                        <button class="btn btn-primary" onclick="setPresetAndInject('only_http', 80, 21)">
                            Run Demo: Only HTTP vs Foreign Packets
                        </button>
                    </div>

                    <!-- Presets -->
                    <div class="preset-bar">
                        <span class="quick-label">Active Preset:</span>
                        <button class="preset-btn highlight" id="p-only-http" onclick="applyPreset('only_http')">Allow ONLY HTTP</button>
                        <button class="preset-btn" id="p-http-https" onclick="applyPreset('http_https')">Allow HTTP + HTTPS</button>
                        <button class="preset-btn" id="p-allow-dns" onclick="applyPreset('allow_dns')">Allow DNS Queries</button>
                        <button class="preset-btn" id="p-block-all" onclick="applyPreset('block_all')">Strict Lockdown</button>
                        <button class="preset-btn" id="p-default" onclick="applyPreset('default')">Default Policy</button>
                    </div>

                    <!-- Service Quick Toggles -->
                    <div class="service-toggles">
                        <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; margin-right: 0.4rem;">Service Toggles:</span>
                        <button class="svc-chip allowed" id="svc-http" onclick="toggleService('http')">HTTP (80) [Allowed]</button>
                        <button class="svc-chip blocked" id="svc-https" onclick="toggleService('https')">HTTPS (443) [Blocked]</button>
                        <button class="svc-chip blocked" id="svc-dns" onclick="toggleService('dns')">DNS (53) [Blocked]</button>
                        <button class="svc-chip blocked" id="svc-telnet" onclick="toggleService('telnet')">Telnet (23) [Blocked]</button>
                        <button class="svc-chip blocked" id="svc-ftp" onclick="toggleService('ftp')">FTP (21) [Blocked]</button>
                        <button class="svc-chip blocked" id="svc-icmp" onclick="toggleService('icmp')">ICMP Ping (0) [Blocked]</button>
                        <button class="svc-chip blocked" id="svc-ssh" onclick="toggleService('ssh')">SSH (22) [Blocked]</button>
                    </div>

                    <!-- Packet Injector Form -->
                    <div class="injector-card">
                        <div style="font-size: 0.82rem; font-weight: 600; color: var(--text-primary); display: flex; justify-content: space-between; align-items: center;">
                            <span>Craft & Inject Test Packet</span>
                            <div style="display: flex; gap: 0.4rem;">
                                <button class="preset-btn" style="font-size: 0.7rem; padding: 2px 8px;" onclick="fillForm('192.168.1.45', '192.168.2.10', 'tcp', 80, 512)">HTTP Packet</button>
                                <button class="preset-btn" style="font-size: 0.7rem; padding: 2px 8px;" onclick="fillForm('192.168.1.88', '192.168.2.20', 'tcp', 21, 128)">FTP Packet</button>
                                <button class="preset-btn" style="font-size: 0.7rem; padding: 2px 8px;" onclick="fillForm('45.33.32.156', '192.168.2.10', 'tcp', 9999, 1400)">Foreign Attacker Packet</button>
                            </div>
                        </div>

                        <div class="injector-grid">
                            <div class="form-group">
                                <label class="form-label">Source IP (Src)</label>
                                <input class="form-input" id="inp-src" value="192.168.1.55" placeholder="192.168.1.x">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Destination IP (Dst)</label>
                                <input class="form-input" id="inp-dst" value="192.168.2.10" placeholder="192.168.2.x">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Protocol</label>
                                <select class="form-select" id="inp-proto">
                                    <option value="tcp">TCP</option>
                                    <option value="udp">UDP</option>
                                    <option value="icmp">ICMP</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Dst Port</label>
                                <input class="form-input" id="inp-port" type="number" value="80" placeholder="80">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Size (Bytes)</label>
                                <input class="form-input" id="inp-size" type="number" value="512" placeholder="Bytes">
                            </div>
                            <div class="form-group">
                                <label class="form-label">&nbsp;</label>
                                <button class="btn btn-primary" style="height: 38px; padding: 0 18px;" onclick="injectPacket()">
                                    Send Packet
                                </button>
                            </div>
                        </div>

                        <!-- ReactBits: BorderTrail on Decision Banner -->
                        <div id="decision-box" class="decision-result">
                            <div class="border-trail"></div>
                            <div class="decision-banner">
                                <span id="decision-badge" class="decision-badge">PERMIT</span>
                                <span id="decision-title" style="font-size: 0.9rem; font-weight: 600;">Packet Permitted</span>
                            </div>
                            <div id="decision-detail" class="decision-detail"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Recent Activity under Lab -->
            <div class="spotlight-card">
                <div class="spotlight-content panel-inner">
                    <div class="panel-header">
                        <div class="panel-title">Inspected Traffic Feed</div>
                    </div>
                    <div class="log-container" style="max-height: 300px;">
                        <table class="log-table">
                            <thead>
                                <tr>
                                    <th>Action</th>
                                    <th>Protocol</th>
                                    <th>Source</th>
                                    <th>Destination</th>
                                    <th>Port</th>
                                    <th>Size</th>
                                    <th>Matched Rule</th>
                                </tr>
                            </thead>
                            <tbody id="lab-log-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- ── TAB 3: About Project ────────────────────── -->
        <section id="view-about" class="view-section">
            <div class="about-grid">
                <div class="spotlight-card about-card">
                    <div class="spotlight-content about-card-inner">
                        <h3>1. Network Topology</h3>
                        <p>Network Monitor replicates an enterprise filtered network environment divided across two distinct subnets connected via a central filtering router:</p>
                        <div class="topo-box">
[Clients Subnet: 192.168.1.0/24]
        | (Workstations / Browsers)
        v
+-------------------------------+
|     Router & ACL Engine       | &lt;-- [Hot-Reload Policy]
|   (First-Match-Wins + Deny)   |
+-------------------------------+
        v
[Servers Subnet: 192.168.2.0/24]
 (Web 80/443, DNS 53, FTP 21)
                        </div>
                        <p>All traffic traversing between the subnets is inspected packet-by-packet by the router ACL engine.</p>
                    </div>
                </div>

                <div class="spotlight-card about-card">
                    <div class="spotlight-content about-card-inner">
                        <h3>2. ACL Engine & Wildcards</h3>
                        <p>The router enforces ordered Access Control Lists inspired by Cisco IOS architectures:</p>
                        <ul>
                            <li><b>Ordered Evaluation:</b> Rules are checked top-to-bottom. The <b>first match wins</b> and immediately decides the action.</li>
                            <li><b>Wildcard Masking:</b> Uses bitwise inverse masks (e.g. <code>0.0.0.255</code> matches an entire <code>/24</code> subnet).</li>
                            <li><b>Implicit Deny:</b> Any packet not matching an explicit <code>permit</code> rule falls through to an automatic deny.</li>
                            <li><b>Hot-Reloading:</b> Policies can be reloaded live without stopping the router or dropping sessions.</li>
                        </ul>
                    </div>
                </div>

                <div class="spotlight-card about-card">
                    <div class="spotlight-content about-card-inner">
                        <h3>3. Foreign Packet Identification</h3>
                        <p>How does the system identify and block unauthorized or foreign traffic?</p>
                        <ul>
                            <li><b>Non-Permitted Protocols:</b> If a policy specifies <i>"Allow ONLY HTTP"</i>, any non-HTTP traffic (FTP, Telnet, SSH, ICMP, DNS) is identified and denied.</li>
                            <li><b>Unexpected Ports:</b> Packets destined for unknown ports (e.g. port 9999 probes or backdoor attempts) are flagged and dropped.</li>
                            <li><b>Rogue External IPs:</b> Any source IP outside <code>192.168.1.0/24</code> attempting access to internal servers is rejected by implicit deny.</li>
                            <li><b>Telemetry:</b> Central Monitor tracks pass/drop ratios, bandwidth, and protocol anomalies in real time.</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="spotlight-card" style="margin-top: 1.25rem;">
                <div class="spotlight-content panel-inner">
                    <div class="panel-header">
                        <div class="panel-title">Active Router ACL Rules (Loaded in Engine)</div>
                    </div>
                    <div style="overflow-x: auto;">
                        <table class="log-table" id="rules-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Action</th>
                                    <th>Protocol</th>
                                    <th>Source / Wildcard</th>
                                    <th>Destination / Wildcard</th>
                                    <th>Port</th>
                                    <th>Rule Description</th>
                                </tr>
                            </thead>
                            <tbody id="rules-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <!-- ── JavaScript ─────────────────────────────────── -->
    <script>
        // ── ReactBits: Squares Background Canvas Implementation ────────
        (function initSquaresBackground() {
            const canvas = document.getElementById('bg-canvas');
            const ctx = canvas.getContext('2d');
            let w, h;
            const size = 38;
            const squares = [];
            let mouse = { x: -1000, y: -1000 };

            function resize() {
                w = canvas.width = window.innerWidth;
                h = canvas.height = window.innerHeight;
            }
            window.addEventListener('resize', resize);
            resize();

            window.addEventListener('mousemove', e => {
                mouse.x = e.clientX;
                mouse.y = e.clientY;
            });

            function draw() {
                ctx.clearRect(0, 0, w, h);
                ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
                ctx.lineWidth = 0.5;

                const cols = Math.ceil(w / size);
                const rows = Math.ceil(h / size);

                for (let i = 0; i < cols; i++) {
                    for (let j = 0; j < rows; j++) {
                        const x = i * size;
                        const y = j * size;
                        const dist = Math.hypot(x + size / 2 - mouse.x, y + size / 2 - mouse.y);

                        if (dist < 180) {
                            const alpha = (1 - dist / 180) * 0.15;
                            ctx.fillStyle = `rgba(6, 182, 212, ${alpha})`;
                            ctx.fillRect(x, y, size, size);
                        }

                        ctx.strokeRect(x, y, size, size);
                    }
                }
                requestAnimationFrame(draw);
            }
            requestAnimationFrame(draw);
        })();

        // ── ReactBits: SpotlightCard Mouse Tracker ─────────────────────
        document.querySelectorAll('.spotlight-card').forEach(card => {
            card.addEventListener('mousemove', e => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                card.style.setProperty('--mouse-x', `${x}px`);
                card.style.setProperty('--mouse-y', `${y}px`);
            });
        });

        // ── ReactBits: Gliding Tab Indicator ───────────────────────────
        function updateTabGlider(targetEl) {
            const glider = document.getElementById('tabGlider');
            if (!targetEl || !glider) return;
            glider.style.width = `${targetEl.offsetWidth}px`;
            glider.style.left = `${targetEl.offsetLeft}px`;
        }

        function switchView(viewName, btnEl) {
            document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

            const target = document.getElementById(`view-${viewName}`);
            if (target) target.classList.add('active');

            if (btnEl) {
                btnEl.classList.add('active');
                updateTabGlider(btnEl);
            }

            if (viewName === 'about') fetchRules();
        }

        function switchViewByName(viewName) {
            const tabs = document.querySelectorAll('.nav-tab');
            const map = { 'dashboard': tabs[0], 'lab': tabs[1], 'about': tabs[2] };
            if (map[viewName]) switchView(viewName, map[viewName]);
        }

        window.addEventListener('load', () => {
            const activeTab = document.querySelector('.nav-tab.active');
            updateTabGlider(activeTab);
        });

        // ── ReactBits: CountUp Numeric Animation ───────────────────────
        const countUpAnimators = {};
        function animateCountUp(elementId, targetValue) {
            const el = document.getElementById(elementId);
            if (!el) return;
            const current = parseInt(el.getAttribute('data-target') || '0', 10);
            if (current === targetValue) return;

            el.setAttribute('data-target', targetValue);
            const start = current;
            const startTime = performance.now();
            const duration = 600;

            if (countUpAnimators[elementId]) cancelAnimationFrame(countUpAnimators[elementId]);

            function step(now) {
                const elapsed = now - startTime;
                const progress = Math.min(elapsed / duration, 1);
                // easeOutQuad
                const ease = 1 - (1 - progress) * (1 - progress);
                const val = Math.round(start + (targetValue - start) * ease);
                el.textContent = val.toLocaleString();

                if (progress < 1) {
                    countUpAnimators[elementId] = requestAnimationFrame(step);
                } else {
                    el.textContent = targetValue.toLocaleString();
                }
            }
            countUpAnimators[elementId] = requestAnimationFrame(step);
        }

        // ── ReactBits: DecryptedText Effect for Rule Descriptions ──────
        function decryptText(element, finalText) {
            if (!element) return;
            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$&*';
            let iteration = 0;
            const maxIterations = 6;
            clearInterval(element._decryptInterval);

            element._decryptInterval = setInterval(() => {
                element.innerText = finalText
                    .split('')
                    .map((char, index) => {
                        if (char === ' ') return ' ';
                        if (index < iteration) return finalText[index];
                        return chars[Math.floor(Math.random() * chars.length)];
                    })
                    .join('');

                if (iteration >= finalText.length) {
                    clearInterval(element._decryptInterval);
                    element.innerText = finalText;
                }
                iteration += 2;
            }, 18);
        }

        // ── Charts Setup ────────────────────────────────
        const COLORS = {
            cyan:   '#06b6d4', blue:   '#3b82f6', purple: '#8b5cf6',
            green:  '#10b981', red:    '#ef4444', amber:  '#f59e0b',
        };

        const chartDefaults = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } },
            },
        };

        const ctxProto = document.getElementById('chart-protocol').getContext('2d');
        const chartProto = new Chart(ctxProto, {
            type: 'doughnut',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [COLORS.cyan, COLORS.blue, COLORS.purple, COLORS.amber],
                    borderWidth: 0,
                    hoverOffset: 6,
                }]
            },
            options: {
                ...chartDefaults,
                cutout: '68%',
                plugins: {
                    ...chartDefaults.plugins,
                    legend: { position: 'right', labels: { color: '#94a3b8', padding: 10, font: { family: 'Inter', size: 11 } } },
                },
            },
        });

        const ctxAction = document.getElementById('chart-action').getContext('2d');
        const chartAction = new Chart(ctxAction, {
            type: 'bar',
            data: {
                labels: ['Allowed (Permit)', 'Blocked (Deny)'],
                datasets: [{
                    data: [0, 0],
                    backgroundColor: ['rgba(16, 185, 129, 0.65)', 'rgba(239, 68, 68, 0.65)'],
                    borderColor: [COLORS.green, COLORS.red],
                    borderWidth: 1.5,
                    borderRadius: 6,
                    barPercentage: 0.45,
                }]
            },
            options: {
                ...chartDefaults,
                plugins: { ...chartDefaults.plugins, legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }, grid: { display: false } },
                    y: { ticks: { color: '#64748b', font: { family: 'Inter', size: 10 } }, grid: { color: 'rgba(30,41,59,0.5)' }, beginAtZero: true },
                },
            },
        });

        const ctxPorts = document.getElementById('chart-ports').getContext('2d');
        const chartPorts = new Chart(ctxPorts, {
            type: 'bar',
            data: { labels: [], datasets: [{ data: [], backgroundColor: 'rgba(139,92,246,0.6)', borderColor: COLORS.purple, borderWidth: 1.5, borderRadius: 5, barPercentage: 0.55 }] },
            options: {
                ...chartDefaults,
                indexAxis: 'y',
                plugins: { ...chartDefaults.plugins, legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(30,41,59,0.4)' }, beginAtZero: true },
                    y: { ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }, grid: { display: false } },
                },
            },
        });

        const ctxTimeline = document.getElementById('chart-timeline').getContext('2d');
        const timelineHistory = { labels: [], allowed: [], blocked: [] };
        const chartTimeline = new Chart(ctxTimeline, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Allowed', data: [], borderColor: COLORS.green, backgroundColor: 'rgba(16,185,129,0.08)', fill: true, tension: 0.35, pointRadius: 0, borderWidth: 2 },
                    { label: 'Blocked', data: [], borderColor: COLORS.red, backgroundColor: 'rgba(239,68,68,0.08)', fill: true, tension: 0.35, pointRadius: 0, borderWidth: 2 },
                ],
            },
            options: {
                ...chartDefaults,
                scales: {
                    x: { ticks: { color: '#64748b', maxRotation: 0, maxTicksLimit: 7, font: { size: 10 } }, grid: { display: false } },
                    y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(30,41,59,0.4)' }, beginAtZero: true },
                },
            },
        });

        const PORT_NAMES = { 80: 'HTTP', 443: 'HTTPS', 53: 'DNS', 21: 'FTP', 23: 'Telnet', 22: 'SSH', 0: 'ICMP Ping', 9999: 'Unknown/Foreign' };
        function portLabel(p) { return PORT_NAMES[p] || `Port ${p}`; }

        // ── Polling & Data Sync ──────────────────────────
        let prevAllowed = 0, prevBlocked = 0;
        let isSimPaused = false;
        let lastSeenPacketTimestamp = 0;

        async function refresh() {
            try {
                const res = await fetch('/api/data');
                const d = await res.json();

                // ReactBits CountUp animation on Stat Values
                animateCountUp('stat-packets', d.summary.total_packets);
                animateCountUp('stat-allowed', d.allowed_blocked.allowed);
                animateCountUp('stat-blocked', d.allowed_blocked.blocked);
                animateCountUp('stat-unexpected', d.unexpected.unexpected_count);

                document.getElementById('stat-volume').textContent = d.summary.total_kb + ' KB transferred';
                document.getElementById('stat-allowed-pct').textContent = d.allowed_blocked.allowed_pct + '% pass rate';
                document.getElementById('stat-blocked-pct').textContent = d.allowed_blocked.blocked_pct + '% drop rate';
                document.getElementById('stat-unexpected-sub').textContent =
                    d.unexpected.unexpected_protocols.length > 0
                        ? `Non-whitelisted: ${d.unexpected.unexpected_protocols.join(', ')}`
                        : 'Probes / Foreign ports';

                // Chart: Protocol
                chartProto.data.labels = Object.keys(d.breakdown.by_protocol).map(p => p.toUpperCase());
                chartProto.data.datasets[0].data = Object.values(d.breakdown.by_protocol);
                chartProto.update('none');

                // Chart: Action
                chartAction.data.datasets[0].data = [d.allowed_blocked.allowed, d.allowed_blocked.blocked];
                chartAction.update('none');

                // Chart: Ports
                chartPorts.data.labels = Object.keys(d.breakdown.by_port).map(p => portLabel(parseInt(p)));
                chartPorts.data.datasets[0].data = Object.values(d.breakdown.by_port);
                chartPorts.update('none');

                // Chart: Timeline
                const now = new Date().toLocaleTimeString();
                const newAllowed = Math.max(0, d.allowed_blocked.allowed - prevAllowed);
                const newBlocked = Math.max(0, d.allowed_blocked.blocked - prevBlocked);
                prevAllowed = d.allowed_blocked.allowed;
                prevBlocked = d.allowed_blocked.blocked;

                timelineHistory.labels.push(now);
                timelineHistory.allowed.push(newAllowed);
                timelineHistory.blocked.push(newBlocked);
                if (timelineHistory.labels.length > 25) {
                    timelineHistory.labels.shift();
                    timelineHistory.allowed.shift();
                    timelineHistory.blocked.shift();
                }
                chartTimeline.data.labels = timelineHistory.labels;
                chartTimeline.data.datasets[0].data = timelineHistory.allowed;
                chartTimeline.data.datasets[1].data = timelineHistory.blocked;
                chartTimeline.update('none');

                // ReactBits: Animated List Row Entrance
                const renderRows = (logs) => logs.slice(-35).reverse().map((e, idx) => `
                    <tr class="${idx === 0 ? 'log-row-enter' : ''}">
                        <td><span class="badge badge-${e.action}">${e.action}</span></td>
                        <td><span class="badge badge-proto">${e.protocol.toUpperCase()}</span></td>
                        <td>${e.src}</td>
                        <td>${e.dst}</td>
                        <td><span class="badge badge-port">${portLabel(e.dst_port)}</span></td>
                        <td>${e.size} B</td>
                        <td style="color: var(--text-dim); font-size: 0.74rem">${e.rule}</td>
                    </tr>
                `).join('');

                const html = renderRows(d.recent_log);
                const tbody = document.getElementById('log-body');
                if (tbody) tbody.innerHTML = html;
                const labTbody = document.getElementById('lab-log-body');
                if (labTbody) labTbody.innerHTML = html;

                document.getElementById('logCount').textContent = `${d.summary.total_packets} packets processed`;
            } catch (err) {
                console.error(err);
            }
        }

        // ── Manual Lab Functions ─────────────────────────
        function fillForm(src, dst, proto, port, size) {
            document.getElementById('inp-src').value = src;
            document.getElementById('inp-dst').value = dst;
            document.getElementById('inp-proto').value = proto;
            document.getElementById('inp-port').value = port;
            document.getElementById('inp-size').value = size;
        }

        async function injectPacket() {
            const pkt = {
                src: document.getElementById('inp-src').value.trim(),
                dst: document.getElementById('inp-dst').value.trim(),
                protocol: document.getElementById('inp-proto').value.trim(),
                dst_port: parseInt(document.getElementById('inp-port').value.trim()),
                size: parseInt(document.getElementById('inp-size').value.trim()) || 512,
            };

            try {
                const res = await fetch('/api/packet/inject', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(pkt),
                });
                const data = await res.json();

                const box = document.getElementById('decision-box');
                const badge = document.getElementById('decision-badge');
                const title = document.getElementById('decision-title');
                const detail = document.getElementById('decision-detail');

                box.classList.add('show');
                if (data.action === 'permit') {
                    badge.className = 'decision-badge permit';
                    badge.textContent = 'PERMIT (ALLOWED)';
                    title.textContent = 'Packet Permitted by Firewall ACL';
                    title.style.color = 'var(--accent-green)';
                    detail.innerHTML = `
                        <b>Packet:</b> ${pkt.protocol.toUpperCase()} ${pkt.src} &rarr; ${pkt.dst}:${portLabel(pkt.dst_port)} (${pkt.size} B)<br>
                        <b>Enforced ACL Rule:</b> <span id="rule-desc-text" style="color:var(--accent-green)">${data.rule}</span><br>
                        <b>Status:</b> Traffic verified and forwarded across router.
                    `;
                } else {
                    badge.className = 'decision-badge deny';
                    badge.textContent = 'DENY (BLOCKED)';
                    title.textContent = 'Foreign / Prohibited Packet Identified & Blocked';
                    title.style.color = 'var(--accent-red)';
                    detail.innerHTML = `
                        <b>Packet:</b> ${pkt.protocol.toUpperCase()} ${pkt.src} &rarr; ${pkt.dst}:${portLabel(pkt.dst_port)} (${pkt.size} B)<br>
                        <b>Enforced Rule:</b> <span id="rule-desc-text" style="color:var(--accent-red)">${data.rule}</span><br>
                        <b>Identification:</b> Non-authorized protocol or foreign destination detected. Packet dropped.
                    `;
                }

                // Apply ReactBits DecryptedText effect to rule text
                const ruleEl = document.getElementById('rule-desc-text');
                if (ruleEl) decryptText(ruleEl, data.rule);

                refresh();
            } catch (err) {
                alert('Failed to send packet: ' + err);
            }
        }

        async function applyPreset(preset) {
            try {
                const res = await fetch('/api/policy/preset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ preset }),
                });
                const d = await res.json();

                document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('highlight'));
                const btnId = `p-${preset.replace('_', '-')}`;
                const qpId = `qp-${preset.replace('_', '-')}`;
                const el = document.getElementById(btnId);
                if (el) el.classList.add('highlight');
                const qpEl = document.getElementById(qpId);
                if (qpEl) qpEl.classList.add('highlight');

                updateSvcChips(preset);
                refresh();
                fetchRules();
            } catch (err) {
                alert('Failed to apply preset: ' + err);
            }
        }

        function updateSvcChips(preset) {
            const isHttpOnly = preset === 'only_http';
            const isAllBlocked = preset === 'block_all';

            setChip('http', !isAllBlocked);
            setChip('https', !isHttpOnly && !isAllBlocked);
            setChip('dns', preset === 'allow_dns');
            setChip('telnet', false);
            setChip('ftp', false);
            setChip('icmp', false);
            setChip('ssh', false);
        }

        function setChip(svc, allowed) {
            const el = document.getElementById(`svc-${svc}`);
            if (!el) return;
            const names = { http:'HTTP (80)', https:'HTTPS (443)', dns:'DNS (53)', telnet:'Telnet (23)', ftp:'FTP (21)', icmp:'ICMP Ping (0)', ssh:'SSH (22)' };
            el.className = allowed ? 'svc-chip allowed' : 'svc-chip blocked';
            el.textContent = `${names[svc]} [${allowed ? 'Allowed' : 'Blocked'}]`;
        }

        async function toggleService(svc) {
            const el = document.getElementById(`svc-${svc}`);
            const isCurrentlyAllowed = el.classList.contains('allowed');
            const newAllowed = !isCurrentlyAllowed;

            try {
                await fetch('/api/policy/service', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service: svc, allowed: newAllowed }),
                });
                setChip(svc, newAllowed);
                refresh();
                fetchRules();
            } catch (err) {
                alert('Failed to toggle service: ' + err);
            }
        }

        async function setPresetAndInject(preset, allowedPort, blockedPort) {
            await applyPreset(preset);
            fillForm('192.168.1.20', '192.168.2.10', 'tcp', allowedPort, 480);
            await injectPacket();

            setTimeout(async () => {
                fillForm('192.168.1.99', '192.168.2.10', 'tcp', blockedPort, 256);
                await injectPacket();
            }, 700);
        }

        async function toggleSim() {
            try {
                const res = await fetch('/api/sim/toggle', { method: 'POST' });
                const d = await res.json();
                isSimPaused = d.is_paused;

                const dot = document.getElementById('simDot');
                const txt = document.getElementById('simText');
                if (isSimPaused) {
                    dot.className = 'status-dot paused';
                    txt.textContent = 'Stream: Paused';
                } else {
                    dot.className = 'status-dot active';
                    txt.textContent = 'Stream: Active';
                }
            } catch (err) {
                console.error(err);
            }
        }

        async function clearLogs() {
            try {
                await fetch('/api/monitor/clear', { method: 'POST' });
                refresh();
            } catch (err) {
                console.error(err);
            }
        }

        async function fetchRules() {
            try {
                const res = await fetch('/api/rules');
                const rules = await res.json();
                const tbody = document.getElementById('rules-body');
                tbody.innerHTML = rules.map((r, i) => `
                    <tr>
                        <td style="color:var(--text-muted)">#${i+1}</td>
                        <td><span class="badge badge-${r.action}">${r.action}</span></td>
                        <td><span class="badge badge-proto">${r.protocol.toUpperCase()}</span></td>
                        <td>${r.src} <span style="color:var(--text-muted); font-size:0.7rem">(${r.src_wildcard})</span></td>
                        <td>${r.dst} <span style="color:var(--text-muted); font-size:0.7rem">(${r.dst_wildcard})</span></td>
                        <td><span class="badge badge-port">${r.dst_port === 0 ? 'ANY' : portLabel(r.dst_port)}</span></td>
                        <td style="color:var(--text-dim)">${r.description}</td>
                    </tr>
                `).join('') + `
                    <tr style="opacity: 0.6">
                        <td style="color:var(--text-muted)">*</td>
                        <td><span class="badge badge-deny">deny</span></td>
                        <td>any</td><td>any</td><td>any</td><td>ANY</td>
                        <td style="color:var(--text-muted)">Implicit deny-all (Drops all non-matching foreign packets)</td>
                    </tr>
                `;
            } catch (err) {
                console.error(err);
            }
        }

        // Initialize
        refresh();
        setInterval(refresh, 1400);
    </script>
</body>
</html>
"""


# ── Flask app factory ─────────────────────────────────────────────

def create_app(sim: Simulation) -> Flask:
    """Create the Flask dashboard app wired to a running simulation."""
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(_DASHBOARD_HTML)

    @app.route("/api/data")
    def api_data():
        data = sim.monitor.dashboard_data()
        data["sim_paused"] = sim.is_paused
        return jsonify(data)

    @app.route("/api/rules")
    def api_rules():
        rules = []
        for i, r in enumerate(sim.router.rules):
            rules.append({
                "index": i,
                "action": r.action.value,
                "protocol": r.protocol,
                "src": r.src,
                "src_wildcard": r.src_wildcard,
                "dst": r.dst,
                "dst_wildcard": r.dst_wildcard,
                "dst_port": r.dst_port,
                "description": r.description,
            })
        return jsonify(rules)

    @app.route("/api/packet/inject", methods=["POST"])
    def api_inject_packet():
        """Manually inject a synthetic or test packet."""
        data = request.get_json() or {}
        pkt = Packet(
            src=data.get("src", "192.168.1.50"),
            dst=data.get("dst", "192.168.2.10"),
            protocol=data.get("protocol", "tcp").lower(),
            dst_port=int(data.get("dst_port", 80)),
            size=int(data.get("size", 512)),
        )
        decision = sim.process_packet(pkt)
        rule_desc = decision.matched_rule.description if decision.matched_rule else "Implicit deny-all"
        return jsonify({
            "action": decision.action.value,
            "rule": rule_desc,
            "packet": pkt.to_dict(),
        })

    @app.route("/api/policy/preset", methods=["POST"])
    def api_policy_preset():
        """Apply a named ACL policy preset (e.g. only_http, block_all)."""
        data = request.get_json() or {}
        preset = data.get("preset", "default")
        sim.router.apply_preset(preset)
        return jsonify({"status": "ok", "preset": preset})

    @app.route("/api/policy/service", methods=["POST"])
    def api_policy_service():
        """Toggle an individual service permission."""
        data = request.get_json() or {}
        service = data.get("service", "")
        allowed = bool(data.get("allowed", False))
        sim.router.set_service_state(service, allowed)
        return jsonify({"status": "ok", "service": service, "allowed": allowed})

    @app.route("/api/sim/toggle", methods=["POST"])
    def api_sim_toggle():
        """Pause or resume auto-generation of packets."""
        if sim.is_paused:
            sim.resume()
        else:
            sim.pause()
        return jsonify({"is_paused": sim.is_paused})

    @app.route("/api/monitor/clear", methods=["POST"])
    def api_monitor_clear():
        """Clear the monitor log and history."""
        sim.monitor.clear()
        return jsonify({"status": "cleared"})

    return app
