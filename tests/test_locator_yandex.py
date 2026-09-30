import asyncio
import json
from pathlib import Path
import hashlib
import time

import pytest

from test_locator import make_history, KEY
from locator_test_package.locator_yandex import (PublicDiskRelay, decrypt_batch, valid_public_url,
    safe_download_url, valid_disk_token, valid_folder, modified_seconds, fingerprint_of, API, FILES_API)

BODY=(Path(__file__).parent/'fixtures/disk-batch.json').read_bytes()
OLD='2026-01-02T03:04:05Z'


def old_item(name,body=BODY,md5=True,modified=OLD):
    item=dict(name=name,type='file',size=len(body),modified=modified)
    if md5:item['md5']=hashlib.md5(body).hexdigest()
    return item


class Disk(PublicDiskRelay):
    def __init__(self,history):
        super().__init__(history,None,'https://disk.yandex.ru/d/test-folder',KEY,'jolion')
        self.files={'jolion-'+('a'*64)+'.jloc':BODY,'latest-jolion.jloc':BODY}
        self.downloads=[]

    def item(self,name):
        body=self.files[name]
        return dict(name=name,type='file',size=len(body),md5=hashlib.md5(body).hexdigest())

    async def request(self,url,params=None):
        if url==API:
            if params.get('path'):
                name=params['path'].lstrip('/')
                return json.dumps(self.item(name)).encode() if name in self.files else None
            items=[self.item(n) for n in sorted(self.files)]
            return json.dumps(dict(type='dir',_embedded=dict(total=len(items),items=items[params['offset']:params['offset']+params['limit']]))).encode()
        if url==API+'/download':
            return json.dumps({'href':'https://downloader.disk.yandex.ru/'+params['path'].lstrip('/')}).encode()
        name=url.rsplit('/',1)[-1];self.downloads.append(name)
        return self.files[name]

class CleanupDisk(Disk):
    """A Disk stub that also records authenticated deletes."""
    def __init__(self,history,**kwargs):
        super().__init__(history);self.trashed=[];self.paths=[];self.delete_status=204
        for key,value in kwargs.items():setattr(self,key,value)
    async def auth_request(self,method,url,params=None):
        assert method=='DELETE' and url==FILES_API
        assert self.token
        path=params['path']
        # The delete must always be <configured folder>/<name that was validated>.
        assert path=='disk:'+self.folder+'/'+path.rsplit('/',1)[-1]
        self.paths.append(path)
        self.trashed.append(path.rsplit('/',1)[-1])
        if self.delete_status==429:
            # Mirror the real method: the backoff must be armed by the relay itself.
            raise self.throttle('120')
        if self.delete_status==403:
            from locator_test_package.locator_yandex import DiskUnauthorized
            raise DiskUnauthorized


def cleaning(history,**kwargs):
    """Build a relay with cleanup enabled and no grace period for the test."""
    return CleanupDisk(history,cleanup_wanted=True,cleanup_enabled=True,cleanup_blocked=False,token='t'*40,
                       folder='/JolionLocator',grace_seconds=0,throttle_ms=0,throttle_until=0.0,**kwargs)


def test_authenticated_encryption_and_url_boundaries():
    assert decrypt_batch(BODY,KEY,'jolion')[0]['latitude']==55.75
    for key,vehicle in [('b'*48,'jolion'),(KEY,'another')]:
        with pytest.raises(Exception):decrypt_batch(BODY,key,vehicle)
    corrupted=json.loads(BODY);corrupted['ciphertext']='A'+corrupted['ciphertext'][1:]
    with pytest.raises(Exception):decrypt_batch(json.dumps(corrupted).encode(),KEY,'jolion')
    assert valid_public_url('https://disk.yandex.ru/d/folder')
    for url in ('http://disk.yandex.ru/d/a','https://attacker.test/a','https://user@disk.yandex.ru/d/a','https://disk.yandex.ru:123/d/a'):
        assert not valid_public_url(url)
    for url in ('https://127.0.0.1/a','https://yandex.ru.attacker.test/a','http://yandex.ru/a'):
        with pytest.raises(ValueError):safe_download_url(url)


def test_import_is_durable_and_retries_do_not_duplicate_points(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=Disk(history);await relay.poll()
        assert relay.status.endswith('синхронизировано')
        assert len(relay.downloads)==2
        with history.app_archive.connect() as db:assert db.execute('SELECT COUNT(*) FROM points').fetchone()[0]==1
        relay=Disk(history);await relay.poll()
        assert not relay.downloads
        assert history.app_latest['latitude']==55.75
    asyncio.run(run())


def test_wrong_key_corrupt_latest_and_restart_can_recover(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=Disk(history);relay.key='b'*48
        await relay.poll()
        assert 'часть файлов' in relay.status
        with history.app_archive.connect() as db:assert db.execute('SELECT COUNT(*) FROM points').fetchone()[0]==0
        relay=Disk(history);relay.files['latest-jolion.jloc']=b'not-json'
        await relay.poll()
        with history.app_archive.connect() as db:assert db.execute('SELECT COUNT(*) FROM points').fetchone()[0]==1
        assert 'часть файлов' in relay.status
    asyncio.run(run())


def test_pages_are_resumed_and_failed_file_is_retried(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=Disk(history)
        relay.files={f'jolion-{i:064x}.jloc':BODY for i in range(24)}
        await relay.poll();assert relay.offset==10
        await relay.poll();assert relay.offset==20
        await relay.poll();assert relay.offset==0
        assert len(relay.downloads)==24
        await relay.poll();assert len(relay.downloads)==24
        # A new file sorting before the previous cursor is found on the next full scan.
        relay.files['jolion-'+('0'*63)+'0.jloc']=b'broken'
        await relay.poll();assert 'часть файлов' in relay.status
    asyncio.run(run())


def test_receipt_is_not_written_if_database_commit_fails(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        original=history.ingest
        async def fail(points):raise OSError('disk full')
        history.ingest=fail
        relay=Disk(history);await relay.poll()
        with history.app_archive.connect() as db:assert db.execute('SELECT COUNT(*) FROM relay_receipts').fetchone()[0]==0
        history.ingest=original;await relay.poll()
        assert history.app_latest is not None
    asyncio.run(run())

def test_closed_relay_does_not_read_or_store(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=Disk(history);relay.close();await relay.poll()
        assert not relay.downloads
        assert history.app_latest is None
    asyncio.run(run())

def test_http_redirect_validation_and_bounded_body(tmp_path):
    class Content:
        def __init__(self,body):self.body=body
        async def iter_chunked(self,size):
            for i in range(0,len(self.body),size):yield self.body[i:i+size]
    class Response:
        def __init__(self,status,body=b'',headers=None):self.status=status;self.content=Content(body);self.headers=headers or {}
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
    class Session:
        def __init__(self,responses):self.responses=iter(responses);self.calls=[]
        def get(self,url,**kwargs):
            assert kwargs['allow_redirects'] is False
            self.calls.append(url);return next(self.responses)
    async def run():
        _,history=make_history(tmp_path)
        session=Session([Response(302,headers={'Location':'https://127.0.0.1/private'})])
        relay=PublicDiskRelay(history,session,'https://disk.yandex.ru/d/test',KEY,'jolion')
        with pytest.raises(ValueError):await relay.request(API)
        assert len(session.calls)==1
        relay.session=Session([Response(200,b'x'*400001)])
        with pytest.raises(ValueError):await relay.request(API)
        relay.session=Session([Response(302,headers={'Location':'https://downloader.disk.yandex.ru/file'}),Response(200,b'ok')])
        assert await relay.request(API)==b'ok'
    asyncio.run(run())


def test_cleanup_needs_a_receipt_and_never_touches_the_live_snapshot(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=cleaning(history)
        imported='jolion-'+'a'*64+'.jloc'
        unseen='jolion-'+'b'*64+'.jloc'
        relay.files={imported:BODY,'latest-jolion.jloc':BODY}
        # The stub listing carries no `modified`, so nothing is old enough yet.
        await relay.poll()
        assert relay.trashed==[]
        # This one appears in the folder but was never imported by this instance.
        relay.files[unseen]=BODY
        # Now allow cleanup and make the already imported file old enough.
        assert relay.cleanup_candidate(old_item(imported))==imported
        assert relay.cleanup_candidate(old_item('latest-jolion.jloc')) is None
        assert relay.cleanup_candidate(old_item(unseen))==unseen   # receipt decides, not age alone
        # No md5/sha256/modified at all: nothing proves which content this is.
        assert relay.cleanup_candidate(dict(name=imported,type='file',size=1)) is None
        items=[old_item(imported),old_item(unseen),old_item('latest-jolion.jloc'),
               old_item(imported,md5=False,modified='2999-01-01T00:00:00Z'),
               old_item(imported,body=b'x')]
        await relay.cleanup(items)
        # The unseen file, the live snapshot, a too-fresh fingerprint and a reused
        # name with new content are all left alone.
        assert relay.trashed==[imported]
        assert relay.cleanup_deleted==1 and relay.cleanup_error is None
    asyncio.run(run())


def test_a_throttled_relay_skips_the_whole_folder_scan(tmp_path):
    """A 5 s interval must not turn into hammering after the API says 429."""
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=Disk(history)
        relay.throttle_until=time.time()+120
        assert relay.throttle_ms==0
        await relay.poll()
        assert relay.downloads==[], "папка опрошена вопреки паузе"
        # Once the pause expires the scan resumes.
        relay.throttle_until=time.time()-1
        await relay.poll()
        assert relay.downloads
    asyncio.run(run())


def test_cleanup_is_off_without_token_and_never_deletes_on_unauthorized(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        # Cleanup never requested: nothing is reported and nothing is deleted.
        relay=CleanupDisk(history)
        assert not relay.cleanup_wanted and not relay.cleanup_enabled
        assert not relay.cleanup_blocked and relay.cleanup_error is None
        await relay.cleanup([old_item('jolion-'+'a'*64+'.jloc')])
        assert relay.trashed==[]
        # Requested without a token: reported, still never deletes.
        relay=CleanupDisk(history);relay.cleanup_wanted=True;relay.cleanup_enabled=True
        relay.cleanup_blocked=True;relay.cleanup_error='unauthorized'
        await relay.cleanup([old_item('jolion-'+'a'*64+'.jloc')])
        assert relay.trashed==[]
        relay._set_status()
        assert 'очистка недоступна' in relay.status
        # A token without write scope must not be retried forever.
        relay=cleaning(history);relay.delete_status=403
        await relay.poll()          # import first so a receipt exists
        assert relay.trashed==[]
        await relay.cleanup([old_item('jolion-'+'a'*64+'.jloc')])
        assert relay.cleanup_blocked and relay.cleanup_error=='unauthorized'
        relay._set_status()
        assert 'очистка недоступна' in relay.status
        await relay.cleanup([old_item('jolion-'+'a'*64+'.jloc')])
        assert len(relay.trashed)==1   # only the rejected attempt, no retry
    asyncio.run(run())


def test_cleanup_backs_off_after_429(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=cleaning(history)
        await relay.poll()          # import first so a receipt exists
        relay.delete_status=429
        await relay.cleanup([old_item('jolion-'+'a'*64+'.jloc')])
        assert relay.cleanup_error=='throttled' and relay.throttle_ms>=120000
        # While throttled the relay must not spend more requests on cleanup.
        attempts=len(relay.trashed);relay.delete_status=204
        await relay.cleanup([old_item('jolion-'+'a'*64+'.jloc')])
        assert len(relay.trashed)==attempts
    asyncio.run(run())


def test_grace_period_protects_recently_uploaded_files(tmp_path):
    assert valid_disk_token('t'*40) and valid_disk_token('a-b_c.d~e'*3)
    for bad in ('', 'short', 'has space', None, 5):assert not valid_disk_token(bad)
    assert valid_folder('/JolionLocator') and valid_folder('/a_b-1')
    for bad in ('JolionLocator', '//x', '/a/b', '/..', '', None):assert not valid_folder(bad)
    assert modified_seconds({'modified':OLD}) is not None
    assert modified_seconds({'modified':'2026-01-02T03:04:05+03:00'}) is not None
    assert modified_seconds({'modified':'nonsense'}) is None
    assert modified_seconds({}) is None
    assert fingerprint_of({'md5':'m'})=='m'
    assert fingerprint_of({'modified':OLD})==OLD
    assert fingerprint_of({})==''
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=cleaning(history);relay.grace_seconds=3600
        recent=old_item('jolion-'+'a'*64+'.jloc',modified='2999-01-01T00:00:00Z')
        assert relay.cleanup_candidate(recent) is None
        await relay.cleanup([recent])
        assert relay.trashed==[]
    asyncio.run(run())


def test_relay_requires_valid_token_and_folder_to_enable_cleanup(tmp_path):
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        for kwargs in ({}, {'token':'short'}, {'folder':'bad'}, {'folder':''}):
            relay=PublicDiskRelay(history,None,'https://disk.yandex.ru/d/f',KEY,'jolion',cleanup=True,**kwargs)
            assert not relay.cleanup_enabled
        relay=PublicDiskRelay(history,None,'https://disk.yandex.ru/d/f',KEY,'jolion',cleanup=True,token='t'*40)
        assert relay.cleanup_enabled and relay.folder=='/JolionLocator'
        # Retention of the grace setting feeds diagnostics, not deletion.
        assert PublicDiskRelay(history,None,'https://disk.yandex.ru/d/f',KEY,'jolion',grace_hours=48).grace_seconds==48*3600
    asyncio.run(run())


def test_delete_can_only_target_the_configured_folder_and_name(tmp_path):
    """A listing entry must never redirect a delete outside disk:<folder>/<ID>-<64hex>.jloc."""
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        relay=cleaning(history)
        await relay.poll()
        # Traversal, wrong case, wrong length, extra suffixes and the live snapshot.
        hostile=['../secret.jloc','../../secret.jloc','/etc/passwd',
                 'jolion-'+'a'*64+'.jloc/../../../x',
                 'jolion-'+'A'*64+'.jloc',            # uppercase hex is not the pattern
                 'jolion-'+'a'*63+'.jloc',            # one digit short
                 'jolion-'+'a'*65+'.jloc',
                 'jolion-'+'a'*64+'.jloc.bak',
                 'jolion-'+'a'*64+'.jloc/',
                 'jolion-other-'+'a'*64+'.jloc',      # belongs to a different vehicle
                 'latest-jolion.jloc','', 'secret']
        for name in hostile:
            assert relay.cleanup_candidate(old_item(name)) is None, name
        await relay.cleanup([old_item(name) for name in hostile])
        assert relay.paths==[]
        # Folders that are root-like or contain traversal never enable cleanup.
        for folder in ('/','//','..','/../..','/a/b','JolionLocator','',None,'/a.b','/a/../b'):
            stub=PublicDiskRelay(history,None,'https://disk.yandex.ru/d/f',KEY,'jolion',
                                 cleanup=True,token='t'*40,folder=folder)
            assert not stub.cleanup_enabled, folder
        # The delete prefix comes from the options, never from the listing: a listing
        # that claims the file lives elsewhere must not move the target.
        item=dict(old_item('jolion-'+'a'*64+'.jloc'),path='/somewhere/else',type='file')
        await relay.cleanup([item])
        assert relay.paths==['disk:/JolionLocator/jolion-'+'a'*64+'.jloc']
    asyncio.run(run())
