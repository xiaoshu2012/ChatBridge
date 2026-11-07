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
