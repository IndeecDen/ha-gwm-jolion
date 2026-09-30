"""Reject integration modules that call a name they never imported.

`python -m compileall` only proves the syntax is valid, and the unit tests cannot
import `__init__.py` because Home Assistant itself is not installed in the test
venv. So a call to a helper that is missing from the import list stays invisible
until the integration is set up on a real instance, where it surfaces as a bare
traceback pointing at one line and no explanation.

pyflakes resolves every name statically and needs no import. Only "undefined name"
is fatal: an unused import is a style matter, while an undefined name is a runtime
crash on a live instance.

Run: .venv\\Scripts\\python.exe tools\\check_names.py
"""
from __future__ import annotations

from pathlib import Path
import sys

try:
    from pyflakes.api import checkPath
except ImportError:  # pragma: no cover - developer setup helper
    print("pyflakes is not installed: python -m pip install pyflakes")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPONENT = ROOT / "custom_components" / "gwm_jolion"


class Collector:
    """Minimal pyflakes reporter that keeps messages instead of printing them."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def unexpectedError(self, filename: str, message: str) -> None:  # noqa: N802
        self.messages.append(f"{filename}: {message}")

    def syntaxError(  # noqa: N802
        self,
        filename: str,
        message: str,
        lineno: int,
        offset: int,
        text: str | None = None,
    ) -> None:
        self.messages.append(f"{filename}:{lineno}:{offset}: {message}")

    def flake(self, message) -> None:
        rendered = message.message % message.message_args
        self.messages.append(f"{message.filename}:{message.lineno}:{message.col}: {rendered}")


def main(argv: list[str] | None = None) -> int:
    # An explicit target lets the checker be pointed at a throwaway copy, which is
    # how its own test proves the report names the file and the line.
    args = sys.argv[1:] if argv is None else argv
    component = Path(args[0]).resolve() if args else DEFAULT_COMPONENT
    if not component.is_dir():
        print(f"not a directory: {component}")
        return 1

    fatal: list[str] = []
    advisory: list[str] = []

    for path in sorted(component.rglob("*.py")):
        collector = Collector()
        checkPath(str(path), collector)
        for text in collector.messages:
            # Keep repo-relative paths so the report matches what a reader greps.
            shown = text.replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", "")
            if ": undefined name " in text or text.endswith(": undefined name"):
                fatal.append(shown)
            else:
                advisory.append(shown)

    for line in advisory:
        print(f"advisory: {line}")
    print()

    if fatal:
        for line in fatal:
            print(f"UNDEFINED NAME: {line}")
        print()
        print(f"{len(fatal)} name(s) are used but never imported or defined.")
        return 1

    print(f"OK: every name in {component.name}/ resolves (pyflakes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
