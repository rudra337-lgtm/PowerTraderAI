"""No bytecode cache in the read-only program folder (#148).

pt_paths says the program folder is read-only at runtime, but Python wrote
app/__pycache__/*.pyc for every module the hub imported, and the runner, trader and
trainer it starts could add more. The launcher, the hub run as a script and every
process the hub starts now run with Python's bytecode writing off.

Everything runs under the isolation guard (app/conftest.py); no network.
"""

import ast
import os
import queue
import subprocess
import sys
import types
from unittest import mock

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pt_hub  # noqa: E402
from test_training_keeps_runner import RunningProc, training_hub  # noqa: E402

Hub = pt_hub.PowerTraderHub
ROOT = os.path.dirname(APP_DIR)


def test_the_launcher_turns_bytecode_writing_off_before_starting_python():
    with open(os.path.join(ROOT, "start_powertrader.bat"), encoding="utf-8") as f:
        lines = [line.strip() for line in f]
    setting = lines.index("set PYTHONDONTWRITEBYTECODE=1")
    start = next(i for i, line in enumerate(lines) if "python.exe" in line)
    assert setting < start


def _is_app_module(name):
    top = name.split(".")[0]
    return os.path.isfile(os.path.join(APP_DIR, f"{top}.py")) or os.path.isdir(
        os.path.join(APP_DIR, top)
    )


def test_the_hub_run_as_a_script_turns_it_off_before_its_first_app_import():
    with open(os.path.join(APP_DIR, "pt_hub.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    first_app_import = next(
        i
        for i, node in enumerate(tree.body)
        if (isinstance(node, ast.Import) and _is_app_module(node.names[0].name))
        or (
            isinstance(node, ast.ImportFrom)
            and node.module
            and _is_app_module(node.module)
        )
    )
    before = ast.unparse(ast.Module(body=tree.body[:first_app_import], type_ignores=[]))
    assert "if __name__ == '__main__':\n    sys.dont_write_bytecode = True" in before


def test_every_process_the_hub_starts_writes_no_bytecode(tmp_path):
    envs = []

    def popen(*args, **kwargs):
        envs.append(kwargs["env"])
        return RunningProc()

    # the neural runner and the trader
    script = tmp_path / "pt_thinker.py"
    script.write_text("# stand-in\n", encoding="utf-8")
    runner = types.SimpleNamespace(hub_dir=str(tmp_path), _reader_thread=mock.Mock())
    with mock.patch.object(pt_hub.subprocess, "Popen", side_effect=popen):
        Hub._start_process(
            runner, pt_hub.ProcInfo("Neural", str(script)), queue.Queue()
        )
        # a trainer
        hub = training_hub(str(tmp_path))
        with mock.patch.object(pt_hub.time, "sleep"):
            Hub.start_trainer_for_selected_coin(hub)
    assert len(envs) == 2
    for env in envs:
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"
        assert env["POWERTRADER_HUB_DIR"] == str(tmp_path)


def test_a_process_started_with_that_environment_writes_no_cache(tmp_path):
    """Python itself honours it: importing a module writes no __pycache__."""
    (tmp_path / "some_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", "import some_module"],
        cwd=str(tmp_path),
        env=pt_hub._child_env(str(tmp_path)),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "__pycache__").exists()
