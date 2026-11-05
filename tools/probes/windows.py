"""Windows-only local evidence collection. Never marks the entire M1 accepted."""

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.probes.common import Check, emit, environment_checks, exit_code
from tools.probes.process import run_isolated


def summarize(reports):
    checks = [
        Check(**check) for report in reports.values() for check in report["checks"]
    ]
    checks += [
        Check("agent_live_acceptance", "blocked", "REAL_AGENT_ACCEPTANCE_REQUIRED"),
        Check("dsh_guard", "blocked", "HISTORICAL_PERMISSIONS_NOT_VERIFIED"),
        Check("qq_limits_media", "blocked", "APPLICATION_CAPABILITIES_NOT_VERIFIED"),
    ]
    return {
        "scope": "windows-probes",
        "windows_acceptance": False,
        "checks": [asdict(check) for check in checks],
        "exit_code": exit_code(checks),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--qq-live",
        action="store_true",
        help="Reply once per owner context with fixed test text",
    )
    args = parser.parse_args()
    prerequisites = environment_checks()
    if platform.machine().lower() not in ("amd64", "x86_64"):
        prerequisites.append(Check("architecture", "blocked", "X64_REQUIRED"))
    if any(check.status != "pass" for check in prerequisites):
        return emit("windows-prerequisites", prerequisites)
    root = Path(__file__).resolve().parents[2]
    base = args.output_dir or Path(os.environ["LOCALAPPDATA"]) / "ChatBridge" / "M1"
    # Unique evidence directory: preserve previous runs rather than overwrite.
    destination = base / (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )
    destination.mkdir(parents=True, exist_ok=False)
    reports = {}
    with tempfile.TemporaryDirectory(prefix="ChatBridge 验证 ") as temp:
        workspace = Path(temp)
        initialized = subprocess.run(
            ["git", "-c", "init.templateDir=", "init", "--quiet", str(workspace)],
            capture_output=True,
            check=False,
            timeout=15,
        )
        if initialized.returncode:
            return emit(
                "windows-prerequisites",
                [Check("temporary_git", "fail", "GIT_INIT_FAILED")],
            )
        jobs = {
            "codex": [
                "agents.py",
                "--agent",
                "codex",
                "--workspace",
                str(workspace),
                "--protocol-only",
            ],
            "dsh": [
                "agents.py",
                "--agent",
                "dsh",
                "--workspace",
                str(workspace),
                "--protocol-only",
            ],
            "qq": ["qqbot.py"] + (["--live"] if args.qq_live else []),
        }
        for name, job in jobs.items():
            try:
                run = run_isolated(
                    [sys.executable, str(root / "tools" / "probes" / job[0]), *job[1:]],
                    env=os.environ.copy(),
                    timeout=180,
                )
                report = json.loads(run.stdout)
                if (
                    not isinstance(report, dict)
                    or run.returncode not in (0, 1, 2)
                    or not isinstance(report.get("checks"), list)
                ):
                    raise ValueError("INVALID_PROBE_REPORT")
                if run.returncode == 1 and not any(
                    check["status"] == "fail" for check in report["checks"]
                ):
                    report["checks"].append(
                        asdict(Check(name, "fail", "NONZERO_WORKER_EXIT"))
                    )
            except (OSError, subprocess.TimeoutExpired, ValueError):
                report = {
                    "checks": [asdict(Check(name, "fail", "PROBE_FAILED_OR_TIMEOUT"))]
                }
            reports[name] = report
            (destination / f"{name}.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    summary = summarize(reports)
    (destination / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
