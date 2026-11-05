"""Isolated released SDK: no prompt, model request or permission change."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.probes.common import Check, emit, installed_version


def clean_environment():
    # This worker is a separate process. Scrub before SDK's inherited-env merge.
    for key in list(os.environ):
        if key.startswith(("CHATBRIDGE_QQ_", "QQ_")):
            del os.environ[key]


def smoke(workspace):
    clean_environment()
    try:
        from deepseek_harness import HarnessClient, HarnessConfig
        from deepseek_harness.errors import JsonRpcError
    except ImportError:
        return [Check("dsh_sdk", "blocked", "SDK_NOT_INSTALLED")]
    checks = []
    with tempfile.TemporaryDirectory(prefix="chatbridge-dsh-") as home:
        for resume in (False, True):
            client = HarnessClient(
                HarnessConfig(
                    dsh_home=home,
                    cwd=str(workspace),
                    profile="sdk",
                    initialize_timeout_seconds=10,
                    request_timeout_seconds=10,
                )
            )
            try:
                client.start()
                client.initialize(
                    cwd=str(workspace),
                    provider="deepseek-official",
                    model="deepseek-v4-flash",
                )
                checks.append(
                    Check("dsh_initialize_" + ("resumed" if resume else "new"), "pass")
                )
                if resume:
                    client.resume_session("chatbridge-empty-session")
                    checks.append(Check("dsh_empty_session_resume", "pass"))
                    try:
                        client.resume_session("chatbridge-absent-session")
                    except JsonRpcError:
                        checks.append(Check("dsh_missing_session_rejected", "pass"))
                    else:
                        checks.append(
                            Check(
                                "dsh_missing_session_rejected",
                                "fail",
                                "UNEXPECTED_RESUME",
                            )
                        )
                actual = Path(
                    client.get_working_directory("chatbridge-empty-session")
                ).resolve()
                checks.append(
                    Check(
                        "dsh_cwd_" + ("resumed" if resume else "new"),
                        "pass" if actual == workspace else "fail",
                        "" if actual == workspace else "WORKSPACE_MISMATCH",
                    )
                )
            except Exception as exc:
                checks.append(Check("dsh_protocol", "fail", type(exc).__name__))
                break
            finally:
                client.close()
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    if not args.workspace.is_dir():
        return emit(
            "sdk-no-model", [Check("workspace", "blocked", "WORKSPACE_NOT_FOUND")]
        )
    try:
        checks = smoke(args.workspace.resolve())
    except Exception as exc:
        checks = [Check("dsh_smoke", "fail", type(exc).__name__)]
    version = installed_version("deepseek-harness-sdk")
    return emit(
        "sdk-no-model", checks, {"deepseek-harness-sdk": version} if version else {}
    )


if __name__ == "__main__":
    raise SystemExit(main())
