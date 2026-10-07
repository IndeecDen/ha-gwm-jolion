"""Every name the integration uses must actually be imported.

The unit tests load single modules by path, so nothing imports `__init__.py`: it
needs Home Assistant, which is not installed in the test venv. A helper missing
from an import list therefore cannot fail a test, and it stays hidden until the
integration is set up on a real instance, where it appears as a traceback with one
line and no message.

This test shells out to the same checker CI runs, so the exit code contract is
covered too.

Run: .venv\\Scripts\\python.exe -m pytest -q tests/test_component_names.py
"""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check_names.py"


def test_every_name_in_the_component_resolves():
    pytest.importorskip("pyflakes", reason="static name check needs pyflakes")
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_checker_reports_the_path_and_the_name(tmp_path):
    """A checker that cannot point at the offending line is not worth running."""
    pytest.importorskip("pyflakes", reason="static name check needs pyflakes")
    component = tmp_path / "gwm_jolion"
    component.mkdir()
    (component / "broken.py").write_text(
        "def handler():\n    return helper(1)\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(CHECKER), str(component)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 1, result.stdout
    assert "broken.py:2" in result.stdout
    assert "helper" in result.stdout


def test_checker_catches_removed_reexport(tmp_path):
    (tmp_path / 'helpers.py').write_text('def other(): pass\n', encoding='utf-8')
    (tmp_path / 'api.py').write_text('from .helpers import snapshot\ndef fetch(): return snapshot()\n', encoding='utf-8')
    result = subprocess.run([sys.executable, str(CHECKER), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "cannot import 'snapshot'" in result.stdout


def test_checker_accepts_reexports_and_rejects_syntax_errors(tmp_path):
    (tmp_path / 'helpers.py').write_text('from .data import snapshot\n', encoding='utf-8')
    (tmp_path / 'data.py').write_text('def snapshot(): return {}\n', encoding='utf-8')
    (tmp_path / 'api.py').write_text('from .helpers import snapshot\ndef fetch(): return snapshot()\n', encoding='utf-8')
    command = [sys.executable, str(CHECKER), str(tmp_path)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    (tmp_path / 'broken.py').write_text('def broken(:\n', encoding='utf-8')
    assert subprocess.run(command, capture_output=True).returncode == 1
