"""Native audit must prove policy transitions and actual host forwarding, not just SDK startup."""

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.probes.common import exit_code
from tools.probes.dsh_native import assess


@pytest.fixture
def events():
    records = []
    for phase in ("seed", "guard", "reject", "question"):
        records.append({"event": "plugin-ready", "phase": phase})
        if phase == "reject":
            records.append({"event": "rejected", "phase": phase, "source": "resume"})
        else:
            records.append(
                {
                    "event": "policy",
                    "phase": phase,
                    "source": "resume" if phase == "guard" else "startup",
                    "before": {
                        "sandbox": "danger-full-access"
                        if phase == "guard"
                        else "workspace-write",
                        "approval": "ask",
                    },
                    "after": {
                        "sandbox": "danger-full-access"
                        if phase == "seed"
                        else "workspace-write",
                        "approval": "ask" if phase == "seed" else "never",
                    },
                    "workspaceMatch": True,
                }
            )
    records.append(
        {"event": "question-error", "phase": "question", "code": "NO_PROVIDER"}
    )
    return records


def statuses(checks):
    return {check.name: (check.status, check.code) for check in checks}


def test_real_policy_evidence_does_not_hide_missing_question_provider(events):
    checks = assess(events, rejected=True)
    result = statuses(checks)
    for name in (
        "native_bundle_loaded",
        "historical_override_observed",
        "native_policy_downgrade",
        "guard_rejects_restore",
    ):
        assert result[name][0] == "pass"
    assert result["native_question_roundtrip"] == ("blocked", "NO_PROVIDER")
    assert exit_code(checks) == 2


def test_sdk_startup_without_loaded_guard_is_failure(events):
    records = [
        record
        for record in events
        if not (record["event"] == "plugin-ready" and record["phase"] == "guard")
    ]
    assert statuses(assess(records, rejected=True))["native_bundle_loaded"][0] == "fail"


def test_restore_without_historical_full_access_is_not_downgrade_proof(events):
    next(
        record
        for record in events
        if record.get("phase") == "guard" and record["event"] == "policy"
    )["before"]["sandbox"] = "workspace-write"
    assert (
        statuses(assess(events, rejected=True))["historical_override_observed"][0]
        == "fail"
    )


@pytest.mark.parametrize(
    ("field", "bad"), [("sandbox", "danger-full-access"), ("approval", "ask")]
)
def test_policy_readback_must_confirm_both_constraints(events, field, bad):
    next(
        record
        for record in events
        if record.get("phase") == "guard" and record["event"] == "policy"
    )["after"][field] = bad
    assert (
        statuses(assess(events, rejected=True))["native_policy_downgrade"][0] == "fail"
    )


def test_workspace_mismatch_cannot_pass_policy_downgrade(events):
    next(
        record
        for record in events
        if record.get("phase") == "guard" and record["event"] == "policy"
    )["workspaceMatch"] = False
    assert (
        statuses(assess(events, rejected=True))["native_policy_downgrade"][0] == "fail"
    )


def test_unrejected_restore_cannot_count_as_guard_failure_handling(events):
    assert (
        statuses(assess(events, rejected=False))["guard_rejects_restore"][0] == "fail"
    )


def test_handshake_capability_or_local_answer_is_not_host_roundtrip(events):
    records = [record for record in events if record["event"] != "question-error"]
    records.append({"event": "question-result", "phase": "question", "matched": True})
    assert statuses(assess(records, rejected=True))["native_question_roundtrip"] == (
        "blocked",
        "HOST_REQUEST_NOT_OBSERVED",
    )
    records.append({"event": "host-question-answered", "phase": "question"})
    checks = assess(records, rejected=True)
    assert statuses(checks)["native_question_roundtrip"][0] == "pass"
    assert (
        exit_code(checks) == 2
    )  # Windows enforcement/model admission remain unexercised.


def test_unexpected_question_error_is_failure_not_missing_capability(events):
    records = copy.deepcopy(events)
    records[-1]["code"] = "BAD_INTENT"
    assert statuses(assess(records, rejected=True))["native_question_roundtrip"] == (
        "fail",
        "QUESTION_REJECTED",
    )


def test_standalone_audit_fails_closed_without_sdk():
    script = Path(__file__).resolve().parents[2] / "tools/probes/dsh_native.py"
    result = subprocess.run(
        [sys.executable, "-S", str(script), "--workspace", str(script.parent)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "SDK_NOT_INSTALLED" in result.stdout
    assert result.stderr == ""


def test_completed_wrong_question_answer_is_failure(events):
    records = [event for event in events if event["event"] != "question-error"]
    records.extend(
        [
            {"event": "host-question-answered", "phase": "question"},
            {"event": "question-result", "phase": "question", "matched": False},
        ]
    )
    assert statuses(assess(records, rejected=True))["native_question_roundtrip"] == (
        "fail",
        "QUESTION_ANSWER_MISMATCH",
    )


def test_cli_launches_sanitized_worker_without_changing_parent(
    monkeypatch, tmp_path, capsys
):
    import json
    import os

    from tools.probes import dsh_native as native

    monkeypatch.setenv("CHATBRIDGE_QQ_APP_SECRET", "fixture-secret")
    monkeypatch.setenv("QQ_APP_SECRET", "fixture-secret")
    monkeypatch.setattr(native, "installed_version", lambda name: "0.2.1rc2")
    monkeypatch.setattr(native.shutil, "which", lambda name: "/fixture/pnpm")
    monkeypatch.setattr(sys, "argv", ["dsh_native.py", "--workspace", str(tmp_path)])
    observed = {}

    def run(argv, *, env, timeout):
        observed.update(env=env, argv=argv)
        return subprocess.CompletedProcess(
            argv,
            2,
            json.dumps(
                {
                    "scope": "dsh-native-lifecycle",
                    "windows_acceptance": False,
                    "checks": [],
                }
            ),
            "",
        )

    monkeypatch.setattr(native, "run_isolated", run)
    assert native.main() == 2
    assert "--worker" in observed["argv"]
    assert "CHATBRIDGE_QQ_APP_SECRET" not in observed["env"]
    assert "QQ_APP_SECRET" not in observed["env"]
    assert os.environ["CHATBRIDGE_QQ_APP_SECRET"] == "fixture-secret"
    assert "fixture-secret" not in capsys.readouterr().out


def test_native_worker_prevents_official_sdk_environment_remerge(
    monkeypatch, tmp_path, capsys
):
    # Characterize the real installed SDK's Popen boundary; never launch a process.
    sdk = pytest.importorskip("deepseek_harness")
    from types import SimpleNamespace

    import deepseek_harness.client as sdk_client

    from tools.probes import dsh_native as native
    from tools.probes.agents import child_environment
    from tools.probes.common import Check

    monkeypatch.setenv("CHATBRIDGE_QQ_APP_SECRET", "fixture-secret")
    monkeypatch.setenv("QQ_APP_SECRET", "fixture-secret")
    captured = {}

    class StoppedAtSpawn(Exception):
        pass

    def spawn(*args, **kwargs):
        captured.update(kwargs["env"])
        raise StoppedAtSpawn

    monkeypatch.setattr(sdk_client.subprocess, "Popen", spawn)

    def audit(workspace):
        client = sdk.HarnessClient(
            sdk.HarnessConfig(
                dsh_home=str(tmp_path / "home"),
                cwd=str(workspace),
                env=child_environment(),
            )
        )
        with pytest.raises(StoppedAtSpawn):
            client.start()
        return [Check("fixture", "blocked", "NOT_A_LIVE_AUDIT")], []

    monkeypatch.setattr(native, "audit", audit)
    args = SimpleNamespace(workspace=tmp_path, events_file=None)
    assert native.worker(args, {}) == 2
    assert "CHATBRIDGE_QQ_APP_SECRET" not in captured
    assert "QQ_APP_SECRET" not in captured
    assert "fixture-secret" not in capsys.readouterr().out
