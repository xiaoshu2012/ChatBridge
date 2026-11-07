"""Reports contain codes and versions, never raw RPC bodies or credentials."""

import importlib.metadata
import inspect
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    code: str = ""


def exit_code(checks):
    if any(c.status == "fail" for c in checks):
        return 1
    if not checks or any(c.status != "pass" for c in checks):
        return 2
    return 0


def emit(scope, checks, versions=None):
    print(
        json.dumps(
            {
                "recorded_at": datetime.now(UTC).isoformat(),
                "scope": scope,
                "os": platform.system(),
                "architecture": platform.machine(),
                "python": platform.python_version(),
                "windows_acceptance": False,
                "versions": versions or {},
                "checks": [asdict(c) for c in checks],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return exit_code(checks)


def environment_checks():
    version = platform.win32_ver()[1].split(".")
    windows = (
        platform.system() == "Windows"
        and len(version) >= 3
        and version[2].isdigit()
        and int(version[2]) >= 22000
    )
    powershell7 = False
    if pwsh := shutil.which("pwsh"):
        try:
            result = subprocess.run(
                [pwsh, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            powershell7 = result.returncode == 0 and result.stdout.strip() == "7"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return [
        Check(
            "windows11",
            "pass" if windows else "blocked",
            "" if windows else "NATIVE_WINDOWS_11_REQUIRED",
        ),
        Check(
            "python312",
            "pass" if sys.version_info[:2] == (3, 12) else "blocked",
            "" if sys.version_info[:2] == (3, 12) else "REQUIRE_PYTHON_312",
        ),
        Check(
            "powershell7",
            "pass" if powershell7 else "blocked",
            "" if powershell7 else "PWSH7_REQUIRED",
        ),
    ]


def installed_version(package):
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def sdk_contract(harness_type, config_type=None):
    missing = []
    if not callable(getattr(harness_type, "resume_session", None)):
        missing.append("resume_session")
    parameters = set(inspect.signature(harness_type).parameters)
    if config_type is not None:
        parameters.update(inspect.signature(config_type).parameters)
    if "on_user_question" not in parameters:
        missing.append("on_user_question")
    return missing
