"""Reject integration modules that call a name they never imported.

`python -m compileall` only proves the syntax is valid, and the unit tests cannot
import `__init__.py` because Home Assistant itself is not installed in the test
venv. So a call to a helper that is missing from the import list stays invisible
until the integration is set up on a real instance, where it surfaces as a bare
traceback pointing at one line and no explanation.

Pyflakes checks names and syntax without importing the integration. An AST pass
also checks explicit relative imports against local module bindings. Unused
imports remain advisory.

Run: .venv\\Scripts\\python.exe tools\\check_names.py
"""
from __future__ import annotations

from pathlib import Path
import ast
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
        self.errors: list[str] = []

    def unexpectedError(self, filename: str, message: str) -> None:  # noqa: N802
        self.errors.append(f"{filename}: {message}")

    def syntaxError(  # noqa: N802
        self,
        filename: str,
        message: str,
        lineno: int,
        offset: int,
        text: str | None = None,
    ) -> None:
        self.errors.append(f"{filename}:{lineno}:{offset}: {message}")

    def flake(self, message) -> None:
        rendered = message.message % message.message_args
        self.messages.append(f"{message.filename}:{message.lineno}:{message.col}: {rendered}")


def local_import_errors(component: Path) -> list[str]:
    """Check names exported by local modules without importing Home Assistant.

    Pyflakes checks the importing scope only: `from .helpers import missing`
    defines a name for it even when helpers cannot actually export that name.
    """
    trees = {}
    exports = {}

    class Bindings(ast.NodeVisitor):
        def __init__(self):
            self.names = set()

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                self.names.add(node.id)

        def visit_FunctionDef(self, node):
            self.names.add(node.name)

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

        def visit_Import(self, node):
            self.names.update(a.asname or a.name.split('.')[0] for a in node.names)

        def visit_ImportFrom(self, node):
            self.names.update(a.asname or a.name for a in node.names)

    for path in component.rglob('*.py'):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError:
            continue  # checkPath reports syntax errors separately
        trees[path] = tree
        bindings = Bindings()
        bindings.visit(tree)
        exports[path] = bindings.names

    errors = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            base = path.parent
            for _ in range(node.level - 1):
                base = base.parent
            target = base.joinpath(*(node.module or '').split('.'))
            module = target.with_suffix('.py') if node.module else target / '__init__.py'
            if not module.is_file():
                module = target / '__init__.py'
            if module not in exports:
                continue
            names = exports[module]
            if '__getattr__' in names or '*' in names:
                continue
            for alias in node.names:
                if alias.name == '*' or alias.name in names:
                    continue
                if module.name == '__init__.py' and ((target / (alias.name + '.py')).is_file()
                        or (target / alias.name / '__init__.py').is_file()):
                    continue
                errors.append(f"{path}:{node.lineno}: cannot import {alias.name!r} from {module.name}")
    return errors


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
        fatal.extend(collector.errors)
        for text in collector.messages:
            # Keep repo-relative paths so the report matches what a reader greps.
            shown = text.replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", "")
            if ": undefined name " in text or text.endswith(": undefined name"):
                fatal.append(shown)
            else:
                advisory.append(shown)

    fatal.extend(local_import_errors(component))

    for line in advisory:
        print(f"advisory: {line}")
    print()

    if fatal:
        for line in fatal:
            print(f"NAME/IMPORT ERROR: {line}")
        print()
        print(f"{len(fatal)} name/import/syntax error(s).")
        return 1

    print(f"OK: every name in {component.name}/ resolves (pyflakes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
