"""A hung worker must not leave the native runtime running after probe timeout."""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from tools.probes.process import run_isolated


def test_timeout_stops_owned_descendants(tmp_path):
    if sys.platform == "win32":
        pytest.skip(
            "POSIX process-group check; native Windows stop is separately blocked"
        )
    pid_file = tmp_path / "child.pid"
    code = """
import subprocess, sys, time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
Path(sys.argv[1]).write_text(str(child.pid))
time.sleep(30)
"""
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            run_isolated(
                [sys.executable, "-c", code, str(pid_file)],
                env=os.environ.copy(),
                timeout=1,
            )
        pid = int(pid_file.read_text())
        proc = Path(f"/proc/{pid}/stat")
        assert not proc.exists() or proc.read_text().split()[2] == "Z"
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_worker_nonzero_exit_is_returned_without_printing_raw_output():
    run = run_isolated(
        [sys.executable, "-c", 'import sys;print("private");sys.exit(2)'],
        env=os.environ.copy(),
        timeout=2,
    )
    assert run.returncode == 2
    assert run.stdout == "private\n"
