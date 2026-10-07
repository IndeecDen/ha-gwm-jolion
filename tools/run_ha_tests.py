"""Run strict HA tests; Windows adapts unused CLI-only POSIX imports.

Linux CI uses the unmodified HA runtime. The Windows adapter deliberately raises
if anything attempts CLI process locking or resource limits. Only asyncio's
local socketpair bypasses the test socket guard. No entities/storage are mocked.
"""
import os
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["GWM_HA_STRICT"] = "1"
if sys.platform == "win32":
    module = ModuleType("fcntl")

    def unsupported(*args, **kwargs):
        raise NotImplementedError("HA CLI process locking requires Linux")

    module.flock = unsupported
    module.LOCK_EX = 2
    module.LOCK_NB = 4
    sys.modules["fcntl"] = module
    resource = ModuleType("resource")
    resource.getrlimit = unsupported
    resource.setrlimit = unsupported
    resource.RLIMIT_NOFILE = 7
    sys.modules["resource"] = resource
    import socket
    original_socketpair = socket.socketpair
    original_socket = socket.socket

    def local_socketpair(*args, **kwargs):
        guarded = socket.socket
        try:
            socket.socket = original_socket
            return original_socketpair(*args, **kwargs)
        finally:
            socket.socket = guarded

    socket.socketpair = local_socketpair

import pytest

raise SystemExit(pytest.main(["-q", "tests/ha", "-o", "asyncio_mode=auto", *sys.argv[1:]]))
