"""Local overrides for the Home Assistant test harness.

pytest-homeassistant-custom-component blocks sockets for the whole session so a
test cannot reach the network. On Linux that is harmless, because asyncio builds
its self-pipe from an AF_UNIX socket. On Windows asyncio falls back to an AF_INET
socket pair, so the blocked `socket.socket()` call makes the event loop
unbuildable and every test errors during fixture setup - before any test body can
run, which is why a fixture cannot fix it in time.

`enable_socket()` only restores `socket.socket`, and the harness patches it once in
its own pytest_configure, so undoing it here sticks for the session. The cloud API
is never reached anyway: the tests replace the client with an AsyncMock.

Run with asyncio auto mode, which the `hass` fixture needs:
    .venv-ha\\Scripts\\python.exe -m pytest -q tests\\ha -o asyncio_mode=auto
"""
import pytest

pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="needs pytest-homeassistant-custom-component",
)

import pytest_socket


@pytest.hookimpl(trylast=True)
def pytest_configure(config) -> None:
    """Undo the harness socket block before any event loop is built.

    trylast matters: the harness installs the block in its own pytest_configure,
    and this hook has to run after it.
    """
    pytest_socket.enable_socket()
