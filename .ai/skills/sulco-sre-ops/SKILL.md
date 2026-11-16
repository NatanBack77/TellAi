---
name: sulco-sre-ops
description: Operational SRE tooling for SULCO to verify container health, monitor process memory, audit readiness probes, and enforce security hardening.
---

# SULCO SRE & Platform Operations Skill

This skill provides operational SRE utilities to audit process readiness, inspect HTTP healthchecks across FastAPI, Streamlit, and React services, and verify resource sizing.

## Quick Start: Health & Latency Probe

Run the bundled script to inspect all three running SULCO services:

```bash
node .ai/skills/sulco-sre-ops/scripts/healthcheck_sulco.cjs
```

### Probe Parameters

- `--api-port <port>`: FastAPI backend port (default: 8000).
- `--app-port <port>`: Streamlit port (default: 8501).
- `--frontend-port <port>`: React/Vite port (default: 5173).

## Container Hardening & Architecture Guide

For deep technical specifications on memory limits, cold-start handling, and read-only filesystem policies, see:
- [container_hardening.md](references/container_hardening.md)
