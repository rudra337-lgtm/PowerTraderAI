"""The trainer's ``trainer_status.json``, read the same way by the hub and the runner.

The pattern trainer writes ``TRAINING`` when it starts, then ``FINISHED`` or ``ERROR``.
A trainer that is killed can write neither, so its file would say ``TRAINING`` until
the coin's next launch: the hub would show the coin as training and the neural runner
would skip it. The hub rewrites the file for trainers it started itself; for one
started anywhere else (a terminal, #145) the trainer records its own process in the
``TRAINING`` status, and a status whose process has gone does not count as training.

A status without a process (an older trainer, or a test) is taken at its word.
"""

import json
import os
from typing import Any, Dict, Optional

try:
    import psutil
except ImportError:  # psutil is a requirement; without it a status is taken at its word
    psutil = None

FILE_NAME = "trainer_status.json"


def this_process() -> Dict[str, Any]:
    """What a trainer adds to its ``TRAINING`` status: its process id and the process's
    start time, which tells a reused process id from the trainer's own."""
    fields: Dict[str, Any] = {"pid": os.getpid()}
    try:
        fields["pid_started"] = psutil.Process().create_time()
    except Exception:
        pass
    return fields


def _process_gone(pid, started) -> Optional[bool]:
    """True if process ``pid`` (started at ``started``) has ended, False if it still
    runs, None if that can't be told."""
    if psutil is None:
        return None
    try:
        proc = psutil.Process(int(pid))
        if started is not None and abs(proc.create_time() - float(started)) > 1.0:
            return True  # the id now belongs to another process
        return proc.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True
    except Exception:  # access denied, or a malformed id
        return None


def is_training(status: Any) -> bool:
    """True if ``status`` (a parsed trainer_status.json) says a trainer is running."""
    if not isinstance(status, dict):
        return False
    if str(status.get("state", "")).upper() != "TRAINING":
        return False
    if status.get("pid") is None:
        return True
    return not _process_gone(status["pid"], status.get("pid_started"))


def read(folder: str) -> Optional[Dict[str, Any]]:
    """The coin folder's trainer status, or None if there is none or it can't be read."""
    try:
        with open(os.path.join(folder, FILE_NAME), encoding="utf-8") as f:
            status = json.load(f)
    except (OSError, ValueError):
        return None
    return status if isinstance(status, dict) else None


def training_in(folder: str) -> bool:
    """True if a trainer is running for the coin whose folder is ``folder``."""
    return is_training(read(folder))
