"""Bounded worker lifecycle for probes; never targets processes by name."""

import os
import signal
import subprocess


def run_isolated(argv, *, env, timeout):
    options = (
        {"start_new_session": True}
        if os.name != "nt"
        else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    )
    with subprocess.Popen(
        argv,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **options,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                # Only this worker's PID/tree; do not kill any named desktop Agent.
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                        timeout=10,
                    )
                finally:
                    if process.poll() is None:
                        process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.communicate(timeout=5)
            raise
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
