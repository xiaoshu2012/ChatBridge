"""Released-SDK worker must fail closed and not inherit QQ credentials."""

import os
import subprocess
import sys
from pathlib import Path

from tools.probes.agents import child_environment


def test_sdk_environment_removes_qq_credentials_without_changing_parent(monkeypatch):
    monkeypatch.setenv("CHATBRIDGE_QQ_APP_SECRET", "fixture-secret")
    monkeypatch.setenv("QQ_APP_SECRET", "other-fixture-secret")
    env = child_environment()
    assert "CHATBRIDGE_QQ_APP_SECRET" not in env
    assert "QQ_APP_SECRET" not in env
    assert os.environ["CHATBRIDGE_QQ_APP_SECRET"] == "fixture-secret"
    assert env["PATH"] == os.environ["PATH"]


def test_sdk_worker_cannot_claim_success_without_dependency():
    script = Path(__file__).resolve().parents[2] / "tools/probes/dsh_smoke.py"
    result = subprocess.run(
        [sys.executable, "-S", str(script), "--workspace", str(script.parent)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2
    assert "SDK_NOT_INSTALLED" in result.stdout
    assert not result.stderr


def test_sdk_worker_strips_qq_environment_before_sdk_start(monkeypatch):
    from tools.probes.dsh_smoke import clean_environment

    monkeypatch.setenv("CHATBRIDGE_QQ_APP_SECRET", "fixture-secret")
    monkeypatch.setenv("QQ_APP_SECRET", "fixture-secret")
    clean_environment()
    assert "CHATBRIDGE_QQ_APP_SECRET" not in os.environ
    assert "QQ_APP_SECRET" not in os.environ
