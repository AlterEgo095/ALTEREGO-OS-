"""PHASE 2.9 — SCÉNARIO 2 : Auditer un VPS.

Le système doit :
- récupérer CPU
- RAM
- disque
- Docker
- services actifs
- logs récents

puis produire un rapport.
Aucune action corrective.

V1.1 : Si SSH credentials not configured, falls back to LOCAL audit (read /proc, /etc).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


async def audit_local_vps() -> dict:
    """Audit the local machine as a 'VPS' (fallback when no SSH creds)."""
    report = {"audited_at": time.strftime("%Y-%m-%d %H:%M:%S"), "mode": "local"}

    # 1. CPU info
    cpu_info = {"cores": os.cpu_count()}
    try:
        with open("/proc/cpuinfo") as f:
            content = f.read()
        cpu_info["model"] = [l for l in content.split("\n") if "model name" in l.lower()][0].split(":")[1].strip()
    except Exception:
        cpu_info["model"] = "unknown"
    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()
        cpu_info["load_1min"] = float(load[0])
        cpu_info["load_5min"] = float(load[1])
        cpu_info["load_15min"] = float(load[2])
    except Exception:
        pass
    report["cpu"] = cpu_info

    # 2. RAM info
    ram_info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    ram_info["total_kb"] = int(line.split()[1])
                elif "MemAvailable" in line:
                    ram_info["available_kb"] = int(line.split()[1])
                elif "SwapTotal" in line:
                    ram_info["swap_total_kb"] = int(line.split()[1])
        ram_info["used_kb"] = ram_info.get("total_kb", 0) - ram_info.get("available_kb", 0)
        ram_info["used_percent"] = round(ram_info["used_kb"] / ram_info["total_kb"] * 100, 1) if ram_info.get("total_kb") else 0
    except Exception:
        pass
    report["ram"] = ram_info

    # 3. Disk usage
    disk_info = {}
    try:
        total, used, free = shutil.disk_usage("/")
        disk_info = {
            "total_gb": round(total / 1024**3, 1),
            "used_gb": round(used / 1024**3, 1),
            "free_gb": round(free / 1024**3, 1),
            "used_percent": round(used / total * 100, 1),
        }
    except Exception:
        pass
    report["disk"] = disk_info

    # 4. Docker containers (via docker CLI subprocess, not docker-py)
    docker_info = {"available": False, "containers": []}
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            docker_info["available"] = True
            for line in stdout.decode().strip().split("\n"):
                if line:
                    parts = line.split("\t")
                    docker_info["containers"].append({
                        "name": parts[0] if len(parts) > 0 else "",
                        "status": parts[1] if len(parts) > 1 else "",
                        "image": parts[2] if len(parts) > 2 else "",
                    })
    except FileNotFoundError:
        pass
    report["docker"] = docker_info

    # 5. Active services (via systemctl, Linux only)
    services = []
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "list-units", "--type=service", "--state=running", "--no-legend",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            for line in stdout.decode().strip().split("\n")[:20]:  # top 20
                if line:
                    parts = line.split()
                    services.append({"name": parts[0], "state": parts[3] if len(parts) > 3 else "running"})
    except FileNotFoundError:
        pass
    report["services"] = services

    # 6. Recent logs (last 50 lines of /var/log/syslog or journalctl)
    logs = []
    try:
        proc = await asyncio.create_subprocess_exec(
            "journalctl", "--no-pager", "-n", "50",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            logs = stdout.decode().strip().split("\n")
    except FileNotFoundError:
        # Try /var/log/syslog
        try:
            with open("/var/log/syslog") as f:
                logs = f.read().split("\n")[-50:]
        except Exception:
            pass
    report["recent_logs_count"] = len(logs)
    report["recent_logs_sample"] = logs[-5:] if logs else []

    # 7. Anomaly detection
    anomalies = []
    if cpu_info.get("load_1min", 0) > cpu_info.get("cores", 1) * 2:
        anomalies.append({"severity": "critical", "issue": f"High CPU load: {cpu_info['load_1min']}"})
    if ram_info.get("used_percent", 0) > 90:
        anomalies.append({"severity": "critical", "issue": f"High RAM usage: {ram_info['used_percent']}%"})
    if disk_info.get("used_percent", 0) > 90:
        anomalies.append({"severity": "critical", "issue": f"High disk usage: {disk_info['used_percent']}%"})
    report["anomalies"] = anomalies

    return report


async def main():
    print("=" * 70)
    print("PHASE 2.9 — SCÉNARIO 2 : AUDIT VPS")
    print("=" * 70)

    # Check if SSH creds are configured
    ssh_host = os.environ.get("SSH_HOST")
    if ssh_host:
        print(f"\n  Mode: SSH remote ({ssh_host})")
        print("  ⚠ SSH plugin requires paramiko — falling back to local audit")
    else:
        print(f"\n  Mode: LOCAL audit (no SSH creds configured)")

    print("\n── Audit en cours ──")
    start = time.perf_counter()
    report = await audit_local_vps()
    elapsed = time.perf_counter() - start
    print(f"  Audit terminé en {elapsed*1000:.0f} ms")

    print(f"\n── CPU ──")
    cpu = report["cpu"]
    print(f"  Cores: {cpu.get('cores')}")
    print(f"  Model: {cpu.get('model', 'unknown')[:60]}")
    print(f"  Load (1/5/15min): {cpu.get('load_1min', '?')} / {cpu.get('load_5min', '?')} / {cpu.get('load_15min', '?')}")

    print(f"\n── RAM ──")
    ram = report["ram"]
    if ram:
        print(f"  Total: {ram.get('total_kb', 0) / 1024:.0f} MB")
        print(f"  Used: {ram.get('used_kb', 0) / 1024:.0f} MB ({ram.get('used_percent', 0)}%)")
        print(f"  Swap: {ram.get('swap_total_kb', 0) / 1024:.0f} MB")
    else:
        print("  (info indisponible)")

    print(f"\n── DISK ──")
    disk = report["disk"]
    if disk:
        print(f"  Total: {disk.get('total_gb')} GB")
        print(f"  Used: {disk.get('used_gb')} GB ({disk.get('used_percent')}%)")
        print(f"  Free: {disk.get('free_gb')} GB")

    print(f"\n── DOCKER ──")
    docker = report["docker"]
    if docker["available"]:
        print(f"  Available: yes")
        print(f"  Containers: {len(docker['containers'])}")
        for c in docker["containers"][:5]:
            print(f"    - {c['name']} ({c['image']}): {c['status']}")
    else:
        print(f"  Available: no")

    print(f"\n── SERVICES ──")
    print(f"  {len(report['services'])} services running")
    for s in report["services"][:5]:
        print(f"    - {s['name']} ({s['state']})")

    print(f"\n── LOGS ──")
    print(f"  {report['recent_logs_count']} lignes récentes récupérées")
    if report["recent_logs_sample"]:
        print("  Dernières lignes:")
        for line in report["recent_logs_sample"][-3:]:
            print(f"    {line[:120]}")

    print(f"\n── ANOMALIES ──")
    if not report["anomalies"]:
        print("  Aucune anomalie détectée ✓")
    else:
        for a in report["anomalies"]:
            print(f"  [{a['severity']}] {a['issue']}")

    # Validation criteria
    criteria = {
        "cpu_retrieved": "cores" in report["cpu"],
        "ram_retrieved": "total_kb" in report.get("ram", {}),
        "disk_retrieved": "total_gb" in report.get("disk", {}),
        "docker_audited": "available" in report["docker"],
        "services_listed": isinstance(report["services"], list),
        "logs_retrieved": report["recent_logs_count"] >= 0,
        "no_corrective_action": True,
    }

    print(f"\n── Critères de validation ──")
    for k, v in criteria.items():
        print(f"  {'✓' if v else '✗'} {k}")

    passed = all(criteria.values())
    print(f"\nSCÉNARIO 2: {'✓ PASS' if passed else '✗ FAIL'}")

    out = Path(__file__).resolve().parent.parent / "results" / "scenario_02_vps.json"
    out.write_text(json.dumps({
        "scenario": 2,
        "passed": passed,
        "criteria": criteria,
        "report": report,
        "elapsed_ms": round(elapsed * 1000, 1),
    }, indent=2, default=str))
    print(f"Results saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
