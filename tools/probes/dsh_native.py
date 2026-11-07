"""Audit released DSH native hooks in an isolated home, with no model prompt."""

import argparse
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.probes.agents import child_environment
from tools.probes.common import Check, emit, installed_version
from tools.probes.dsh_smoke import clean_environment
from tools.probes.process import run_isolated

PHASES = ("seed", "guard", "reject", "question")


def assess(events, *, rejected):
    def find(phase, event):
        return next(
            (
                item
                for item in events
                if item.get("phase") == phase and item.get("event") == event
            ),
            {},
        )

    loaded = all(find(phase, "plugin-ready") for phase in PHASES)
    seed, guard = find("seed", "policy"), find("guard", "policy")
    historical = (
        seed.get("after", {}).get("sandbox") == "danger-full-access"
        and guard.get("before", {}).get("sandbox") == "danger-full-access"
        and guard.get("source") == "resume"
    )
    constrained = (
        guard.get("after") == {"sandbox": "workspace-write", "approval": "never"}
        and guard.get("workspaceMatch") is True
    )
    declined = rejected and bool(find("reject", "rejected"))
    checks = [
        Check(
            "native_bundle_loaded",
            "pass" if loaded else "fail",
            "" if loaded else "HOOK_NOT_LOADED",
        ),
        Check(
            "historical_override_observed",
            "pass" if historical else "fail",
            "" if historical else "HISTORY_NOT_PROVEN",
        ),
        Check(
            "native_policy_downgrade",
            "pass" if constrained else "fail",
            "" if constrained else "POLICY_NOT_CONFIRMED",
        ),
        Check(
            "guard_rejects_restore",
            "pass" if declined else "fail",
            "" if declined else "RESTORE_NOT_REJECTED",
        ),
    ]
    question, error = (
        find("question", "question-result"),
        find("question", "question-error"),
    )
    if question.get("matched") is True and find("question", "host-question-answered"):
        checks.append(Check("native_question_roundtrip", "pass"))
    elif question.get("matched") is True:
        checks.append(
            Check("native_question_roundtrip", "blocked", "HOST_REQUEST_NOT_OBSERVED")
        )
    elif question:
        checks.append(
            Check("native_question_roundtrip", "fail", "QUESTION_ANSWER_MISMATCH")
        )
    elif error.get("code") == "NO_PROVIDER":
        checks.append(Check("native_question_roundtrip", "blocked", "NO_PROVIDER"))
    elif error and error.get("code") != "ASK_ABORTED":
        checks.append(Check("native_question_roundtrip", "fail", "QUESTION_REJECTED"))
    else:
        checks.append(
            Check("native_question_roundtrip", "blocked", "QUESTION_NOT_COMPLETED")
        )
    checks.extend(
        [
            Check("first_model_request", "blocked", "MODEL_BOUNDARY_NOT_EXERCISED"),
            Check(
                "windows_permission_enforcement",
                "blocked",
                "NATIVE_WRITE_BOUNDARY_NOT_EXERCISED",
            ),
        ]
    )
    return checks


def read_events(path):
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if path.exists()
        else []
    )


def answer_question(client, trace):
    incoming = queue.Queue()

    def receive():
        try:
            incoming.put(client.next_request())
        except Exception:
            pass

    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    answered = False
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            request = incoming.get_nowait()
            questions = request.payload.get("questions", [])
            if (
                request.method == "user-question/ask"
                and len(questions) == 1
                and questions[0].get("id") == "m1-question"
                and questions[0].get("options") == [{"label": "Probe answer"}]
                and questions[0].get("intent") is None
            ):
                client.respond(
                    request.id,
                    {"answers": [{"id": "m1-question", "selected": ["Probe answer"]}]},
                )
                answered = True
            else:
                client.respond_error(
                    request.id, code=-32601, message="Unsupported probe request"
                )
        except queue.Empty:
            pass
        if any(
            event.get("event") in ("question-result", "question-error")
            for event in read_events(trace)
        ):
            break
        time.sleep(0.05)
    return answered


def audit(workspace):
    from deepseek_harness import HarnessClient, HarnessConfig
    from deepseek_harness.errors import JsonRpcError
    from deepseek_harness.models import InitializeResponse
    from deepseek_harness_runtime import resolve_bundled_launch_args

    bundle = Path(__file__).with_name("dsh_native_bundle").resolve()
    with tempfile.TemporaryDirectory(prefix="ChatBridge DSH 验证 ") as folder:
        root = Path(folder)
        home, trace = root / "home", root / "events.jsonl"
        env = child_environment()
        env.update(
            DSH_HOME=str(home),
            CHATBRIDGE_NATIVE_TRACE=str(trace),
            CHATBRIDGE_NATIVE_WORKSPACE=str(workspace),
        )
        installed = run_isolated(
            [
                *resolve_bundled_launch_args(),
                "plugin",
                "--profile",
                "sdk",
                "add",
                bundle.as_uri(),
            ],
            env=env,
            timeout=60,
        )
        if installed.returncode:
            return [Check("native_bundle_install", "fail", "BUNDLE_INSTALL_FAILED")], []
        rejected, host_answered = False, False
        for phase in PHASES:
            child_env = dict(env, CHATBRIDGE_NATIVE_PHASE=phase)
            client = HarnessClient(
                HarnessConfig(
                    dsh_home=str(home),
                    cwd=str(workspace),
                    profile="sdk",
                    env=child_env,
                    initialize_timeout_seconds=30,
                    request_timeout_seconds=10,
                )
            )
            try:
                client.start()
                params = {
                    "cwd": str(workspace),
                    "provider": "deepseek-official",
                    "model": "deepseek-v4-flash",
                }
                if phase == "question":
                    params["capabilities"] = {"userQuestions": True}
                    client.request(
                        "initialize",
                        params,
                        response_model=InitializeResponse,
                        timeout_seconds=30,
                    )
                else:
                    client.initialize(**params)
                if not any(
                    event.get("phase") == phase and event.get("event") == "plugin-ready"
                    for event in read_events(trace)
                ):
                    return [
                        Check("native_bundle_loaded", "fail", "HOOK_NOT_LOADED")
                    ], read_events(trace)
                if phase in ("guard", "reject"):
                    client.resume_session("chatbridge-policy-history")
                else:
                    client.get_working_directory(
                        "chatbridge-policy-history"
                        if phase == "seed"
                        else "chatbridge-question"
                    )
                if phase == "question":
                    host_answered = answer_question(client, trace)
            except JsonRpcError as exc:
                if phase == "reject" and "CHATBRIDGE_POLICY_GUARD_REJECTED" in str(exc):
                    rejected = True
                else:
                    return [
                        Check("native_lifecycle", "fail", "UNEXPECTED_RPC_ERROR")
                    ], read_events(trace)
            finally:
                client.close()
        events = read_events(trace)
        if host_answered:
            events.append({"event": "host-question-answered", "phase": "question"})
        return assess(events, rejected=rejected), events


def worker(args, versions):
    # SDK start() overlays config.env onto os.environ; filtering an overlay alone
    # cannot remove keys. This dedicated worker must scrub its own environment.
    clean_environment()
    try:
        checks, events = audit(args.workspace.resolve())
        if args.events_file:
            with args.events_file.open("x", encoding="utf-8") as output:
                json.dump(events, output, ensure_ascii=False, indent=2)
                output.write("\n")
    except Exception as exc:
        checks = [Check("dsh_native_audit", "fail", type(exc).__name__)]
    return emit("dsh-native-lifecycle", checks, versions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--events-file",
        type=Path,
        help="Create a new sanitized evidence file; never overwrite",
    )
    args = parser.parse_args()
    versions = {
        name: version
        for name in ("deepseek-harness-sdk", "deepseek-harness-runtime-bin")
        if (version := installed_version(name))
    }
    if len(versions) != 2:
        return emit(
            "dsh-native-lifecycle",
            [Check("dsh_sdk", "blocked", "SDK_NOT_INSTALLED")],
            versions,
        )
    if len(set(versions.values())) != 1:
        return emit(
            "dsh-native-lifecycle",
            [Check("dsh_sdk", "fail", "SDK_RUNTIME_VERSION_MISMATCH")],
            versions,
        )
    if not args.workspace.is_dir():
        return emit(
            "dsh-native-lifecycle",
            [Check("workspace", "blocked", "WORKSPACE_NOT_FOUND")],
            versions,
        )
    if not shutil.which("pnpm"):
        return emit(
            "dsh-native-lifecycle",
            [Check("plugin_manager", "blocked", "PNPM_REQUIRED")],
            versions,
        )
    if args.worker:
        return worker(args, versions)
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--workspace",
        str(args.workspace.resolve()),
    ]
    if args.events_file:
        argv.extend(["--events-file", str(args.events_file.resolve())])
    try:
        run = run_isolated(argv, env=child_environment(), timeout=300)
        report = json.loads(run.stdout)
        if (
            run.returncode not in (0, 1, 2)
            or not isinstance(report, dict)
            or report.get("scope") != "dsh-native-lifecycle"
            or report.get("windows_acceptance") is not False
            or not isinstance(report.get("checks"), list)
        ):
            raise ValueError("INVALID_AUDIT_REPORT")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return emit(
            "dsh-native-lifecycle",
            [Check("dsh_native_worker", "fail", "WORKER_FAILED_OR_INVALID_REPORT")],
            versions,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
