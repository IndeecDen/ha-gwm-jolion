"""Local overrides for the Home Assistant test harness.

pytest-homeassistant-custom-component blocks sockets so a test cannot reach the
network. On Linux that is harmless: asyncio builds its self-pipe from an AF_UNIX
socket, which the harness guard allows. On Windows asyncio uses an AF_INET socket
pair instead, so the guard rejects it, the event loop cannot be constructed, and
every test errors while the `event_loop` fixture is set up - the loop is left half
built, which is where the later `'_ssock'` AttributeError comes from.

The harness disables sockets again for every test from its own
`pytest_runtest_setup`, and a conftest hook of the same name does not run after it,
so the block is lifted right before each fixture is built instead. That is the last
moment before the event loop exists.

The cloud API is never reached anyway: the tests replace the client with an
AsyncMock.

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
    """Undo the harness block before anything else builds an event loop."""
    pytest_socket.enable_socket()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_fixture_setup(fixturedef, request):
    """Let sockets through while a fixture - and so any event loop - is built.

    tryfirst keeps this wrapper outside the pytest-asyncio one, so the release
    happens before that wrapper asks the fixture for its result.
    """
    pytest_socket.enable_socket()
    yield
