"""Catch false success when Windows, released SDK APIs or QQ identity is absent."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.probes.common import Check, exit_code, sdk_contract
from tools.probes.qqbot import authorized_target

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("checks", "want"),
    [
        ([Check("x", "pass")], 0),
        ([Check("x", "blocked")], 2),
        ([Check("x", "fail"), Check("y", "blocked")], 1),
        ([], 2),
    ],
)
def test_exit_codes_distinguish_failure_and_missing_prerequisites(checks, want):
    assert exit_code(checks) == want


def test_missing_resume_cannot_be_hidden_by_lazy_start():
    class LazyOnly:
        def start_session(self):
            pass

        def close(self):
            pass

    assert sdk_contract(LazyOnly) == ["resume_session", "on_user_question"]


def test_sdk_wrapper_config_is_inspected_instead_of_kwargs():
    class Config:
        def __init__(self, *, on_user_question=None):
            pass

    class Harness:
        def __init__(self, config=None, **kwargs):
            pass

        def resume_session(self):
            pass

    assert sdk_contract(Harness, Config) == []


def test_windows_10_cannot_count_as_windows_11(monkeypatch):
    import tools.probes.common as common

    monkeypatch.setattr(common.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        common.platform, "win32_ver", lambda: ("10", "10.0.19045", "", "")
    )
    assert common.environment_checks()[0].status == "blocked"


def test_qq_identity_and_group_mention_gate():
    env = {
        "CHATBRIDGE_QQ_C2C_OPENID": "private-owner",
        "CHATBRIDGE_QQ_GROUP_OPENID": "allowed-group",
        "CHATBRIDGE_QQ_GROUP_MEMBER_OPENID": "group-owner",
    }

    def event(kind, sender, group=None):
        return {
            "op": 0,
            "t": kind,
            "d": {
                "id": "message-fixture",
                "author": {"user_openid": sender, "member_openid": sender},
                "group_openid": group,
            },
        }

    assert authorized_target(event("C2C_MESSAGE_CREATE", "private-owner"), env) == (
        "users",
        "private-owner",
        "message-fixture",
    )
    assert authorized_target(
        event("GROUP_AT_MESSAGE_CREATE", "group-owner", "allowed-group"), env
    ) == ("groups", "allowed-group", "message-fixture")
    assert authorized_target(event("C2C_MESSAGE_CREATE", "group-owner"), env) is None
    assert (
        authorized_target(
            event("GROUP_MESSAGE_CREATE", "group-owner", "allowed-group"), env
        )
        is None
    )
    assert (
        authorized_target(
            event("GROUP_AT_MESSAGE_CREATE", "other", "allowed-group"), env
        )
        is None
    )
    assert (
        authorized_target(
            event("GROUP_AT_MESSAGE_CREATE", "group-owner", "other-group"), env
        )
        is None
    )
    assert authorized_target(event("C2C_MESSAGE_CREATE", ""), {}) is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"op": 0, "t": "C2C_MESSAGE_CREATE", "d": None},
        {"op": 0, "t": "C2C_MESSAGE_CREATE", "d": {"author": []}},
    ],
)
def test_malformed_qq_events_are_not_authorized(payload):
    assert authorized_target(payload, {}) is None


@pytest.mark.parametrize("script", ["agents.py", "qqbot.py"])
def test_cli_preflight_does_not_leak_environment_or_claim_live_success(script):
    env = dict(os.environ, CHATBRIDGE_QQ_APP_SECRET="never-print-this-secret")
    args = [sys.executable, str(ROOT / "tools/probes" / script)]
    if script == "agents.py":
        args += ["--agent", "codex", "--workspace", str(ROOT)]
    run = subprocess.run(
        args, env=env, text=True, capture_output=True, timeout=15, check=False
    )
    assert run.returncode == 2
    assert "never-print-this-secret" not in run.stdout + run.stderr
    report = json.loads(run.stdout)
    assert report["scope"] == "preflight"
    assert report["windows_acceptance"] is False
    assert any(c["status"] == "blocked" for c in report["checks"])


def test_codex_npm_wrapper_resolves_native_executable_without_shell(
    tmp_path, monkeypatch
):
    import tools.probes.agents as agents

    wrapper = tmp_path / "codex.cmd"
    wrapper.write_text("fixture wrapper")
    executable = (
        tmp_path
        / "node_modules/@openai/codex/vendor/x86_64-pc-windows-msvc/codex/codex.exe"
    )
    executable.parent.mkdir(parents=True)
    executable.write_text("fixture native binary")
    monkeypatch.delenv("CHATBRIDGE_CODEX_BIN", raising=False)
    monkeypatch.setattr(agents.shutil, "which", lambda _: str(wrapper))
    assert agents.resolve_codex() == str(executable)


def test_invalid_explicit_codex_binary_does_not_fall_back(tmp_path, monkeypatch):
    from tools.probes.agents import resolve_codex

    monkeypatch.setenv("CHATBRIDGE_CODEX_BIN", str(tmp_path / "missing.exe"))
    assert resolve_codex() is None
