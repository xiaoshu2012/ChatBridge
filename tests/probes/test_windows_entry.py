"""Local entry must detect blockers, preserve reports and never manufacture acceptance."""

import json
import subprocess
import sys
from pathlib import Path

from tools.probes.windows import summarize


def test_failed_probe_takes_priority_over_missing_prerequisite():
    result = summarize(
        {
            "codex": {"checks": [{"name": "rpc", "status": "fail", "code": "EOF"}]},
            "dsh": {
                "checks": [{"name": "guard", "status": "blocked", "code": "MISSING"}]
            },
        }
    )
    assert result["exit_code"] == 1
    assert result["windows_acceptance"] is False


def test_passing_smoke_cannot_complete_m1():
    result = summarize(
        {"codex": {"checks": [{"name": "initialize", "status": "pass", "code": ""}]}}
    )
    assert result["exit_code"] == 2
    assert result["windows_acceptance"] is False
    assert any(
        check["code"] == "REAL_AGENT_ACCEPTANCE_REQUIRED" for check in result["checks"]
    )


def test_windows_entry_rejects_linux_without_creating_output(tmp_path):
    if sys.platform == "win32":
        return
    script = Path(__file__).resolve().parents[2] / "tools/probes/windows.py"
    result = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path / "evidence")],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["scope"] == "windows-prerequisites"
    assert not (tmp_path / "evidence").exists()
