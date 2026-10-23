"""trainer_status.json: a trainer that was killed does not count as training (#145).

The trainer records its process in its TRAINING status. The hub and the neural runner
read the status through trainer_status, so a TRAINING whose process has gone (a
terminal-started trainer that was killed) no longer holds the coin as "training".

Everything runs under the isolation guard (app/conftest.py); no network.
"""

import json
import os
import subprocess
import sys
import time
import types
from unittest import mock

import psutil
import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pt_data_provider  # noqa: E402
import pt_hub  # noqa: E402
import trainer_status  # noqa: E402

Hub = pt_hub.PowerTraderHub


def ended_process():
    """The id and start time of a process that has since ended."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        started = psutil.Process(proc.pid).create_time()
    finally:
        proc.kill()
        proc.wait(timeout=30)
    return proc.pid, started


def write_status(folder, **status):
    with open(os.path.join(folder, "trainer_status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f)


# --- the rule -------------------------------------------------------------------------


def test_a_running_trainer_is_training():
    assert trainer_status.is_training(
        {"state": "TRAINING", **trainer_status.this_process()}
    )


def test_a_trainer_whose_process_has_ended_is_not_training():
    pid, started = ended_process()
    assert not trainer_status.is_training(
        {"state": "TRAINING", "pid": pid, "pid_started": started}
    )


def test_a_reused_process_id_is_not_the_trainer():
    """The id belongs to a live process, but one that started at another time."""
    assert not trainer_status.is_training(
        {"state": "TRAINING", "pid": os.getpid(), "pid_started": 1.0}
    )


def test_a_status_without_a_process_is_taken_at_its_word():
    """An older trainer, or a test, writes no process."""
    assert trainer_status.is_training({"state": "TRAINING"})


@pytest.mark.parametrize(
    "status", [{"state": "FINISHED"}, {"state": "ERROR"}, {}, None, "TRAINING", []]
)
def test_anything_else_is_not_training(status):
    assert not trainer_status.is_training(status)


def test_a_status_that_cannot_be_read_is_not_training(tmp_path):
    assert trainer_status.read(str(tmp_path)) is None
    (tmp_path / "trainer_status.json").write_text("{not json", encoding="utf-8")
    assert trainer_status.read(str(tmp_path)) is None
    assert not trainer_status.training_in(str(tmp_path))


# --- the runner -----------------------------------------------------------------------


@pytest.fixture
def runner():
    cwd = os.getcwd()
    sys.modules.pop("pt_thinker", None)
    with mock.patch.object(pt_data_provider, "get_data_provider"):
        import pt_thinker
    yield pt_thinker
    os.chdir(cwd)
    sys.modules.pop("pt_thinker", None)


def test_the_runner_no_longer_skips_a_coin_whose_trainer_was_killed(runner):
    folder = runner.coin_folder("SOL")
    os.makedirs(folder, exist_ok=True)
    write_status(folder, state="TRAINING", **trainer_status.this_process())
    assert runner._training_in_progress("SOL")
    pid, started = ended_process()
    write_status(folder, state="TRAINING", pid=pid, pid_started=started)
    assert not runner._training_in_progress("SOL")


# --- the hub --------------------------------------------------------------------------


def stub_hub(folder):
    return types.SimpleNamespace(
        trainers={},
        coins=["ETH"],
        coin_folders={"ETH": folder},
        last_training_times={},
        settings={},
    )


def test_the_hub_no_longer_lists_a_killed_trainer_as_running(tmp_path):
    folder = str(tmp_path)
    hub = stub_hub(folder)
    write_status(folder, state="TRAINING", **trainer_status.this_process())
    assert Hub._running_trainers(hub) == ["ETH"]
    pid, started = ended_process()
    write_status(folder, state="TRAINING", pid=pid, pid_started=started)
    assert Hub._running_trainers(hub) == []


def test_a_coin_whose_trainer_was_killed_reads_as_trained_again(tmp_path):
    """Its earlier model and stamp are still there: only the stale TRAINING hid it."""
    folder = str(tmp_path)
    hub = stub_hub(folder)
    with open(os.path.join(folder, "trainer_last_training_time.txt"), "w") as f:
        f.write(str(time.time()))
    write_status(folder, state="TRAINING", **trainer_status.this_process())
    assert not Hub._coin_is_trained(hub, "ETH")
    pid, started = ended_process()
    write_status(folder, state="TRAINING", pid=pid, pid_started=started)
    assert Hub._coin_is_trained(hub, "ETH")
