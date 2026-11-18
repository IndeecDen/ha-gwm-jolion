"""Offline access probes: never use real credentials or perform writes."""
import asyncio
import json

import pytest
from aiohttp import ClientError

import test_locator  # Install the lightweight integration package used by tests.
from locator_test_package import locator_yandex as disk

TOKEN = 'synthetic-secret-token'
FOLDER = '/PrivateSyntheticFolder'
VERDICTS = ('status', 'token', 'folder', 'public_folder', 'write_access')


class Response:
    def __init__(self, status=200, payload=None, headers=None):
        self.status = status
        self.body = json.dumps(payload or {}).encode()
        self.headers = headers or {}
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        yield self.body


class Session:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response


def relay(session):
    # cleanup=True: the access probes only run for a relay that will delete, and
    # these tests exist to exercise those probes.
    return disk.PublicDiskRelay(None, session, 'https://disk.yandex.ru/d/synthetic',
                                'synthetic-key', 'jolion', token=TOKEN, folder=FOLDER, cleanup=True)


@pytest.mark.parametrize('url', [
    'https://downloader.disk.yandex.ru/file',
    'https://yandex.ru/file',
    'https://cloud-api.yandex.net.evil.test/v1/disk/resources',
    'https://cloud-api.yandex.net/v1/disk/resources?redirect=elsewhere',
])
def test_oauth_never_sent_outside_exact_resources_endpoint(url):
    session = Session(Response(204))
    with pytest.raises(ValueError):
        asyncio.run(relay(session).auth_request('DELETE', url))
    assert session.calls == []


def test_access_success_is_read_only_sanitized_and_cached():
    session = Session(*(Response(payload={'type': 'dir'}) for _ in range(4)))
    client = relay(session)
    assert client.last_diagnostics is None
    result = asyncio.run(client.check_access())
    assert {k: result[k] for k in VERDICTS} == {
        'status': 'ok', 'token': 'ok', 'folder': 'ok',
        'public_folder': 'ok', 'write_access': 'ok'}
    assert isinstance(result['checked_at'], int) and result['checked_at'] > 0
    assert result['summary'] and 'доступн' in result['summary'].lower()
    assert result['hint'] == ''
    assert client.last_diagnostics == result
    assert [call[:2] for call in session.calls] == [
        ('GET', disk.FILES_API), ('GET', disk.FILES_API), ('GET', disk.WRITE_API),
        ('GET', disk.API)]
    assert session.calls[0][2]['params'] == {'path': 'disk:/', 'fields': 'type'}
    assert session.calls[1][2]['params'] == {'path': 'disk:' + FOLDER, 'fields': 'type'}
    # The write probe asks for an upload link and never follows it, so nothing is created.
    assert session.calls[2][2]['params'] == {
        'path': 'disk:' + FOLDER + '/.gwm-jolion-probe', 'overwrite': 'false'}
    assert session.calls[3][2]['params'] == {'public_key': client.public_url, 'fields': 'type'}
    for _, url, kwargs in session.calls:
        assert kwargs['allow_redirects'] is False
        assert kwargs.get('headers', {}).get('Authorization') == (
            'OAuth ' + TOKEN if url in (disk.FILES_API, disk.WRITE_API) else None)
    for private in (TOKEN, FOLDER, client.public_url, client.key):
        assert private not in json.dumps(result)
    # Probing access never deletes anything, whatever the cleanup settings say.
    assert client.cleanup_deleted == 0 and all(method == 'GET' for method, _, _ in session.calls)


@pytest.mark.parametrize('http, expected, overall, attempts', [
    (401, 'unauthorized', 'auth_error', 1), (403, 'forbidden', 'auth_error', 1),
    (404, 'not_found', 'error', 1), (429, 'throttled', 'transient_error', 3),
    (500, 'unavailable', 'transient_error', 3), (503, 'unavailable', 'transient_error', 3),
    (302, 'unexpected_response', 'error', 1), (400, 'unexpected_response', 'error', 1),
])
@pytest.mark.parametrize('stage', ['token', 'folder', 'public_folder'])
def test_http_failures_are_classified_without_following_redirects(http, expected, overall, attempts, stage, monkeypatch):
    monkeypatch.setattr(disk, 'uniform', lambda a, b: 0, raising=False)
    good = lambda: Response(payload={'type': 'dir'})
    bad = lambda: Response(http, {'error': TOKEN + FOLDER}, {'Location': 'https://evil.test/'})
    # write probe only runs when token and folder are readable, so only that stage sees it
    responses = {'token': [bad() for _ in range(attempts)] + [good()],
                 'folder': [good()] + [bad() for _ in range(attempts)] + [good()],
                 'public_folder': [good(), good(), good()] + [bad() for _ in range(attempts)]}[stage]
    session = Session(*responses)
    client = relay(session)
    result = asyncio.run(client.check_access())
    assert result[stage] == expected
    assert result['status'] == overall
    if stage == 'token':
        assert result['folder'] == 'not_checked'
        assert result['write_access'] == 'not_checked'
    if stage == 'folder':
        assert result['write_access'] == 'not_checked'
    if stage != 'public_folder':
        assert result['public_folder'] == 'ok'
    assert len(session.calls) == len(responses)
    assert client.last_diagnostics == result
    assert TOKEN not in json.dumps(result) and FOLDER not in json.dumps(result)
    assert client.throttle_until == 0 and not client.cleanup_blocked
    # Every failure is described in plain language with one actionable hint.
    assert result['summary'] and disk.PROBE_LABELS[stage] in result['summary']


@pytest.mark.parametrize('http, expected, overall', [
    (403, 'forbidden', 'auth_error'), (401, 'unauthorized', 'auth_error'),
    (507, 'no_space', 'error'), (302, 'unexpected_response', 'error'),
])
def test_write_scope_is_verified_without_creating_files(http, expected, overall, monkeypatch):
    monkeypatch.setattr(disk, 'uniform', lambda a, b: 0, raising=False)
    session = Session(Response(payload={'type': 'dir'}), Response(payload={'type': 'dir'}),
                      Response(http), Response(payload={'type': 'dir'}))
    result = asyncio.run(relay(session).check_access())
    assert result['write_access'] == expected
    assert result['status'] == overall
    assert result['token'] == result['folder'] == result['public_folder'] == 'ok'
    assert [call[1] for call in session.calls][2] == disk.WRITE_API
    # No PUT/POST is ever issued: the upload link is only requested.
    assert all(call[0] == 'GET' for call in session.calls)
    assert result['hint'], 'write failures must explain what to fix'
    assert TOKEN not in json.dumps(result)


def test_write_probe_is_skipped_when_read_access_fails():
    session = Session(Response(403), Response(payload={'type': 'dir'}))
    result = asyncio.run(relay(session).check_access())
    assert result['token'] == 'forbidden'
    assert result['write_access'] == 'not_checked'
    assert len(session.calls) == 2


@pytest.mark.parametrize('token, folder, cleanup, token_state, folder_state, status, calls', [
    ('', FOLDER, False, 'not_required', 'not_checked', 'ok', 1),
    ('bad', FOLDER, False, 'not_required', 'not_checked', 'ok', 1),
    (TOKEN, FOLDER, False, 'not_required', 'not_checked', 'ok', 1),
    ('', FOLDER, True, 'not_configured', 'not_checked', 'error', 1),
    (TOKEN, '/a/../private', True, 'ok', 'invalid_config', 'error', 2),
])
def test_missing_or_invalid_config_still_checks_public_folder(token, folder, cleanup, token_state,
                                                              folder_state, status, calls):
    session = Session(*(Response(payload={'type': 'dir'}) for _ in range(calls)))
    client = disk.PublicDiskRelay(None, session, 'https://disk.yandex.ru/d/synthetic',
                                 'synthetic-key', 'jolion', token=token, folder=folder, cleanup=cleanup)
    result = asyncio.run(client.check_access())
    assert result['token'] == token_state
    assert result['folder'] == folder_state
    assert result['public_folder'] == 'ok'
    assert result['status'] == status
    assert len(session.calls) == calls


def test_read_only_mode_is_not_reported_as_a_failure():
    """Only deletion needs the token, so a read-only relay stays healthy."""
    session = Session(Response(payload={'type': 'dir'}))
    result = asyncio.run(disk.PublicDiskRelay(None, session, 'https://disk.yandex.ru/d/synthetic',
                                              'synthetic-key', 'jolion').check_access())
    assert result['status'] == 'ok'
    assert result['token'] == 'not_required'
    assert result['public_folder'] == 'ok'
    assert 'Токен не нужен' in result['summary']
    assert result['hint'] == ''
    title, body = disk.notify_text(result)
    assert title == 'Яндекс.Диск: доступ есть' and 'Что сделать' not in body


@pytest.mark.parametrize('error', [TimeoutError(TOKEN), OSError(FOLDER), ClientError(TOKEN)])
def test_transport_failures_are_transient_and_do_not_expose_details(error, monkeypatch):
    monkeypatch.setattr(disk, 'uniform', lambda a, b: 0, raising=False)
    session = Session(error, error, error, Response(payload={'type': 'dir'}))
    client = relay(session)
    result = asyncio.run(client.check_access())
    assert result['status'] == 'transient_error'
    assert result['token'] == ('timeout' if isinstance(error, TimeoutError) else 'network_error')
    assert result['public_folder'] == 'ok'
    assert len(session.calls) == 4
    assert TOKEN not in json.dumps(result) and FOLDER not in json.dumps(result)


def test_throttled_probe_recovers_within_one_budget(monkeypatch):
    monkeypatch.setattr(disk, 'uniform', lambda a, b: 0, raising=False)
    session = Session(Response(429), *(Response(payload={'type': 'dir'}) for _ in range(4)))
    result = asyncio.run(relay(session).check_access())
    assert {k: result[k] for k in VERDICTS} == {
        'status': 'ok', 'token': 'ok', 'folder': 'ok',
        'public_folder': 'ok', 'write_access': 'ok'}
    assert len(session.calls) == 5


def test_retries_stop_at_the_attempt_limit(monkeypatch):
    monkeypatch.setattr(disk, 'uniform', lambda a, b: 0, raising=False)
    session = Session(Response(500), Response(500), Response(500),
                      Response(payload={'type': 'dir'}))
    client = relay(session)
    result = asyncio.run(client.check_access())
    assert result['token'] == 'unavailable' and result['status'] == 'transient_error'
    assert len(session.calls) == 4  # three token attempts, then the public probe


def test_each_probe_has_a_deadline_including_body_read(monkeypatch):
    class Stalled(Response):
        async def iter_chunked(self, size):
            await asyncio.Event().wait()
            yield b''
    monkeypatch.setattr(disk, 'ACCESS_TIMEOUT', 0.01, raising=False)
    client = relay(Session(Stalled(), Stalled()))
    async def run():
        return await asyncio.wait_for(client.check_access(), timeout=1)
    result = asyncio.run(run())
    assert result['token'] == result['public_folder'] == 'timeout'
    assert result['status'] == 'transient_error'


@pytest.mark.parametrize('body, expected', [
    (b'not json containing synthetic-secret-token', 'invalid_response'),
    (b'[]', 'invalid_response'), (b'null', 'invalid_response'),
    (b'{}', 'invalid_response'), (b'{"type": "file"}', 'not_folder'),
    (b'{"type": "unexpected"}', 'invalid_response'),
    (json.dumps({'type': 'dir', 'padding': 'x' * disk.MAX_FILE}).encode(), 'invalid_response'),
])
def test_untrusted_metadata_is_bounded_and_sanitized(body, expected):
    bad = Response()
    bad.body = body
    client = relay(Session(Response(payload={'type': 'dir'}), bad,
                           Response(payload={'type': 'dir'})))
    result = asyncio.run(client.check_access())
    assert result['folder'] == expected
    assert result['status'] == 'error'
    assert result['public_folder'] == 'ok'
    assert TOKEN not in json.dumps(result)


def test_cancellation_preserves_last_completed_diagnostics():
    async def run():
        entered = asyncio.Event()
        class Stalled(Response):
            async def iter_chunked(self, size):
                entered.set()
                await asyncio.Event().wait()
                yield b''
        session = Session(*(Response(payload={'type': 'dir'}) for _ in range(4)), Stalled())
        client = relay(session)
        completed = await client.check_access()
        completed['token'] = 'caller-mutated'
        assert client.last_diagnostics['token'] == 'ok'
        previous = client.last_diagnostics.copy()
        task = asyncio.create_task(client.check_access())
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.last_diagnostics == previous
        assert len(session.calls) == 5
    asyncio.run(run())


def test_forbidden_and_unauthorized_get_different_advice():
    """A 403 means the token is known to Yandex but lacks Disk scope — not an expired token."""
    forbidden = asyncio.run(relay(Session(Response(403), Response(payload={'type': 'dir'}))).check_access())
    unauthorized = asyncio.run(relay(Session(Response(401), Response(payload={'type': 'dir'}))).check_access())
    assert forbidden['status'] == unauthorized['status'] == 'auth_error'
    assert 'перевыпуст' in forbidden['hint'] and 'Диск' in forbidden['hint']
    assert 'недействителен' not in forbidden['hint']
    assert 'отозван' in unauthorized['hint']
    assert forbidden['hint'] != unauthorized['hint']


def test_notification_text_tells_the_user_what_to_do():
    ok = {'status': 'ok', 'token': 'ok', 'folder': 'ok', 'write_access': 'ok', 'public_folder': 'ok',
          'summary': 'Все проверки пройдены: токен, папка, запись и публичная папка доступны.', 'hint': ''}
    title, body = disk.notify_text(ok)
    assert title == 'Яндекс.Диск: доступ есть'
    assert 'Что сделать' not in body

    failed = {'status': 'auth_error', 'token': 'forbidden', 'folder': 'not_checked',
              'write_access': 'not_checked', 'public_folder': 'ok',
              'summary': 'Диск отклонил доступ: токен — нет прав.', 'hint': 'Перевыпустите токен.'}
    title, body = disk.notify_text(failed)
    assert title == 'Яндекс.Диск: доступа нет'
    assert 'Диск отклонил доступ' in body and 'Что сделать: Перевыпустите токен.' in body

    title, body = disk.notify_text(None)
    assert title == 'Яндекс.Диск: проверка не удалась' and 'журнале' in body
