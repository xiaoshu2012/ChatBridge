"""Prerequisite audit and no-model protocol smoke; see docs/validation."""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.probes.common import (
    Check,
    emit,
    environment_checks,
    installed_version,
    sdk_contract,
)
from tools.probes.process import run_isolated
from tools.probes.rpc import RpcClient, RpcError


def child_environment():
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CHATBRIDGE_QQ_", "QQ_"))
    }


def resolve_codex():
    if configured := os.environ.get("CHATBRIDGE_CODEX_BIN"):
        path = Path(configured).expanduser()
        return (
            str(path)
            if path.is_file() and path.suffix.lower() not in (".cmd", ".bat")
            else None
        )
    found = shutil.which("codex")
    if not found or Path(found).suffix.lower() not in (".cmd", ".bat"):
        return found
    # npm's Windows launcher is a shell wrapper. Use the package's native binary.
    packages = Path(found).parent / "node_modules" / "@openai"
    for directory in (
        packages / "codex",
        packages / "codex-win32-x64",
        packages / "codex" / "node_modules" / "@openai" / "codex-win32-x64",
    ):
        binary = directory / "vendor" / "x86_64-pc-windows-msvc" / "codex" / "codex.exe"
        if binary.is_file():
            return str(binary)
    return None


def codex_checks():
    return [
        Check(
            "codex_executable",
            "pass" if resolve_codex() else "blocked",
            "" if resolve_codex() else "CODEX_NATIVE_BINARY_NOT_FOUND",
        )
    ]


async def codex_protocol(workspace):
    checks = []
    with tempfile.TemporaryDirectory(prefix="chatbridge-codex-") as home:
        env = child_environment()
        env["CODEX_HOME"] = home
        async with RpcClient(
            [resolve_codex(), "app-server", "--listen", "stdio://"],
            env=env,
            cwd=workspace,
        ) as client:
            initialized = await client.request(
                "initialize",
                {
                    "clientInfo": {"name": "chatbridge_m1_probe", "version": "0.0.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            if not isinstance(initialized, dict):
                return [Check("codex_initialize", "fail", "INVALID_HANDSHAKE")]
            checks.append(Check("codex_initialize", "pass"))
            await client.notify("initialized")
            started = await client.request(
                "thread/start",
                {
                    "cwd": str(workspace),
                    "approvalPolicy": "never",
                    "sandbox": "workspace-write",
                    "ephemeral": True,
                },
            )
            if not isinstance(started.get("thread", {}).get("id"), str):
                return checks + [
                    Check("codex_thread_start", "fail", "MISSING_THREAD_ID")
                ]
            checks.append(Check("codex_thread_start_no_model", "pass"))
            try:
                await client.request(
                    "thread/resume",
                    {
                        "threadId": "00000000-0000-0000-0000-000000000000",
                        "cwd": str(workspace),
                        "approvalPolicy": "never",
                        "sandbox": "workspace-write",
                    },
                )
            except RpcError:
                checks.append(Check("codex_missing_session_rejected", "pass"))
            else:
                checks.append(
                    Check("codex_missing_session_rejected", "fail", "UNEXPECTED_RESUME")
                )
    return checks


def dsh_contract_checks():
    if not installed_version("deepseek-harness-sdk"):
        return [Check("dsh_sdk", "blocked", "SDK_NOT_INSTALLED")]
    from deepseek_harness import DeepSeekHarness, DeepSeekHarnessConfig

    missing = sdk_contract(DeepSeekHarness, DeepSeekHarnessConfig)
    return [
        Check(
            "dsh_released_sdk_contract",
            "blocked" if missing else "pass",
            "MISSING_" + "_AND_".join(missing) if missing else "",
        ),
        Check("dsh_permission_guard", "blocked", "RELEASE_GUARD_NOT_VERIFIED"),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("codex", "dsh"), required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--protocol-only",
        action="store_true",
        help="No model/QQ traffic; does not constitute M1 acceptance",
    )
    args = parser.parse_args()
    versions = {
        key: value
        for key in ("deepseek-harness-sdk", "deepseek-harness-runtime-bin")
        if (value := installed_version(key))
    }
    checks = codex_checks() if args.agent == "codex" else dsh_contract_checks()
    if not args.workspace.is_dir():
        checks.append(Check("workspace", "blocked", "WORKSPACE_NOT_FOUND"))
    if not args.protocol_only:
        return emit(
            "preflight",
            environment_checks()
            + checks
            + [Check("live_acceptance", "blocked", "USE_WINDOWS_ACCEPTANCE_CHECKLIST")],
            versions,
        )
    if args.agent == "codex" and all(c.status == "pass" for c in checks):
        try:
            checks += asyncio.run(codex_protocol(args.workspace.resolve()))
        except Exception as exc:
            checks.append(Check("codex_protocol", "fail", type(exc).__name__))
    if (
        args.agent == "dsh"
        and installed_version("deepseek-harness-sdk")
        and args.workspace.is_dir()
    ):
        try:
            run = run_isolated(
                [
                    sys.executable,
                    str(Path(__file__).with_name("dsh_smoke.py")),
                    "--workspace",
                    str(args.workspace.resolve()),
                ],
                env=child_environment(),
                timeout=150,
            )
            report = json.loads(run.stdout)
            checks += [Check(**check) for check in report["checks"]]
            if run.returncode not in (0, 2):
                checks.append(Check("dsh_smoke_worker", "fail", "WORKER_FAILED"))
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
            checks.append(
                Check("dsh_smoke_worker", "fail", "INVALID_OR_TIMEOUT_WORKER")
            )
    return emit("protocol-only", checks, versions)


if __name__ == "__main__":
    raise SystemExit(main())
