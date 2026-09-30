"""Read authenticated encrypted GPS batches from a public Yandex Disk folder.

Cleanup deletes only archive files that this Home Assistant instance has already
imported and committed. The proof is a row in ``relay_receipts``, which is written
after the SQLite transaction in :meth:`Archive.ingest` succeeds. Files without that
receipt, live snapshots, and files too young to be trusted twice are never deleted.
"""
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .locator_protocol import validate

API = 'https://cloud-api.yandex.net/v1/disk/public/resources'
FILES_API = 'https://cloud-api.yandex.net/v1/disk/resources'
MAX_FILE = 400000
# Option keys live in locator.py; this module only needs the behaviour defaults.
DEFAULT_FOLDER = '/JolionLocator'
DEFAULT_GRACE_HOURS = 24
MAX_FILE_DELETES = 25
THROTTLE_MIN_MS = 60000
THROTTLE_MAX_MS = 300000


class DiskThrottled(Exception):
    """The Disk API refused the current request rate."""

    def __init__(self, retry_after=None):
        super().__init__('Диск ограничил частоту запросов')
        self.retry_after = retry_after


class DiskUnauthorized(Exception):
    """The stored OAuth token cannot delete files."""


def valid_disk_token(value):
    """Match the OAuth token format the Android app accepts."""
    return isinstance(value, str) and re.fullmatch(r'[!-~]{10,2048}', value) is not None


def valid_folder(value):
    """Accept a single root-level folder, exactly as the Android app does."""
    return isinstance(value, str) and re.fullmatch(r'/[A-Za-z0-9_-]{1,80}', value or '') is not None


def archive_pattern(vehicle):
    """Immutable history files only. The live snapshot is never a cleanup target."""
    return re.compile(re.escape(vehicle) + r'-[a-f0-9]{64}\.jloc\Z')


def latest_pattern(vehicle):
    return re.compile(r'latest-' + re.escape(vehicle) + r'\.jloc\Z')


def fingerprint_of(item):
    """Return the content identity Yandex reports for one listed file."""
    return str(item.get('md5') or item.get('sha256') or item.get('modified') or '')


def modified_seconds(item):
    raw = str(item.get('modified') or '')
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def valid_public_url(value):
    try:
        p=urlsplit(value)
        return p.scheme=='https' and p.hostname in ('disk.yandex.ru','disk.yandex.com','yadi.sk') and not p.username and p.port in (None,443) and bool(p.path.strip('/'))
    except (ValueError,TypeError):
        return False


def safe_download_url(value):
    p=urlsplit(value)
    host=p.hostname or ''
    if p.scheme!='https' or p.username or p.port not in (None,443) or not any(host==s or host.endswith('.'+s) for s in ('yandex.ru','yandex.net','yandex.com')):
        raise ValueError('Untrusted download address')
    return value


def decrypt_batch(body, key, vehicle):
    if len(body)>MAX_FILE:raise ValueError('File too large')
    envelope=json.loads(body)
    if type(envelope.get('version')) is not int or envelope['version']!=1 or envelope.get('vehicle_id')!=vehicle:
        raise ValueError('Wrong relay envelope')
    nonce=base64.b64decode(envelope['nonce'],validate=True)
    if len(nonce)!=12:raise ValueError('Invalid nonce')
    ciphertext=base64.b64decode(envelope['ciphertext'],validate=True)
    secret=hashlib.sha256(key.encode('utf-8')).digest()
    plaintext=AESGCM(secret).decrypt(nonce,ciphertext,('jolion-disk-v1:'+vehicle).encode())
    return validate(json.loads(plaintext))


class PublicDiskRelay:
    def __init__(self, history, session, public_url, key, vehicle, *, token='',
                 folder=DEFAULT_FOLDER, cleanup=False, grace_hours=DEFAULT_GRACE_HOURS):
        if not valid_public_url(public_url):raise ValueError('Invalid public folder URL')
        self.history,self.session=history,session
        self.public_url,self.key,self.vehicle=public_url,key,vehicle
        self.namespace=hashlib.sha256((public_url+'\0'+key).encode()).hexdigest()
        self.offset=0
        self.lock=asyncio.Lock()
        self.status='Ожидание Яндекс.Диска'
        self.closed=False
        # Deletion stays off until the user supplies a token and a valid folder.
        self.token=token if valid_disk_token(token) else ''
        self.folder=folder if valid_folder(folder) else ''
        self.cleanup_wanted=bool(cleanup)
        self.cleanup_enabled=bool(cleanup and self.token and self.folder)
        # "blocked" means the user asked for cleanup but it cannot run.
        self.cleanup_blocked=self.cleanup_wanted and not self.cleanup_enabled
        self.cleanup_error='unauthorized' if (self.cleanup_wanted and not self.token) else None
        self.cleanup_deleted=0
        self.grace_seconds=max(3600,int(grace_hours)*3600)
        self.throttle_ms=0
        self.throttle_until=0.0
        self.archive=archive_pattern(vehicle)
        self.latest=latest_pattern(vehicle)

    def close(self):
        self.closed=True

    async def request(self,url,params=None):
        for _ in range(4):
            safe_download_url(url)
            async with self.session.get(url,params=params,allow_redirects=False) as response:
                if response.status in (301,302,303,307,308):
                    url=response.headers['Location'];params=None;continue
                if response.status==404:return None
                if response.status==429:raise self.throttle(response.headers.get('Retry-After'))
                if response.status!=200:raise ValueError('Disk HTTP '+str(response.status))
                data=bytearray()
                async for block in response.content.iter_chunked(16384):
                    data.extend(block)
                    if len(data)>MAX_FILE:raise ValueError('Response too large')
                return bytes(data)
        raise ValueError('Too many redirects')

    def throttle(self,retry_after=None):
        """Back off after a 429 instead of repeating the same request next tick."""
        # Retry-After is usually seconds but may be an HTTP date; ignore the latter.
        try:requested=int(retry_after or 0)*1000
        except (TypeError,ValueError):requested=0
        self.throttle_ms=min(THROTTLE_MAX_MS,max(self.throttle_ms*2,requested,THROTTLE_MIN_MS))
        self.throttle_until=time.time()+self.throttle_ms/1000
        return DiskThrottled(retry_after)

    def _receipt(self,name,fingerprint):
        return hashlib.sha256((self.namespace+'\0'+name+'\0'+fingerprint).encode()).hexdigest()

    async def auth_request(self,method,url,params=None):
        """Own-files API call. The token is only sent to the verified Disk host."""
        if not self.token:raise DiskUnauthorized
        safe_download_url(url)
        headers={'Authorization':'OAuth '+self.token}
        async with self.session.request(method,url,params=params,headers=headers,allow_redirects=False) as response:
            if response.status in (401,403):raise DiskUnauthorized
            if response.status==429:raise self.throttle(response.headers.get('Retry-After'))
            # Yandex answers a trash move with 204, or 200/202 when it is asynchronous.
            if response.status not in (200,202,204):raise ValueError('Disk HTTP '+str(response.status))

    async def meta(self,path=None,**extra):
        params={'public_key':self.public_url,'fields':'type,name,size,md5,sha256,modified,_embedded.items.name,_embedded.items.type,_embedded.items.size,_embedded.items.md5,_embedded.items.sha256,_embedded.items.modified,_embedded.total',**extra}
        if path is not None:params['path']=path
        body=await self.request(API,params)
        return json.loads(body) if body is not None else None

    async def import_file(self,item):
        name=item.get('name','')
        if item.get('type')!='file' or not (self.archive.fullmatch(name) or self.latest.fullmatch(name)):return False
        if not 0<int(item.get('size',0))<=MAX_FILE:raise ValueError('Invalid relay file size')
        fingerprint=fingerprint_of(item)
        receipt=self._receipt(name,fingerprint)
        seen=await self.history.hass.async_add_executor_job(self.history.app_archive.relay_seen,receipt)
        if fingerprint and seen:return False
        link=await self.request(API+'/download',{'public_key':self.public_url,'path':'/'+name})
        if link is None:raise ValueError('Relay file disappeared')
        body=await self.request(safe_download_url(json.loads(link)['href']))
        if body is None:raise ValueError('Download unavailable')
        points=decrypt_batch(body,self.key,self.vehicle)
        if self.closed:raise asyncio.CancelledError()
        await self.history.ingest(points)
        # A crash between ingest and receipt is safe: point IDs are idempotent.
        await self.history.hass.async_add_executor_job(self.history.app_archive.relay_mark,receipt)
        return True

    def cleanup_candidate(self,item):
        """Return a file name only when deleting it cannot lose data.

        The live snapshot is always excluded, a missing fingerprint means Yandex
        never confirmed the content, and the grace period survives any chance to
        re-check a file this instance already committed.
        """
        name=item.get('name','')
        if item.get('type')!='file' or not self.archive.fullmatch(name):return None
        if not fingerprint_of(item):return None
        modified=modified_seconds(item)
        if modified is None or time.time()-modified<self.grace_seconds:return None
        return name

    async def cleanup(self,items):
        """Move already imported files to the Disk trash. Never raises."""
        if not self.cleanup_enabled or self.closed or self.cleanup_blocked:return
        if time.time()<self.throttle_until:
            self.cleanup_error='throttled';return
        self.cleanup_error=None
        for item in items:
            if self.cleanup_deleted>=MAX_FILE_DELETES or self.closed:return
            name=self.cleanup_candidate(item)
            if name is None:continue
            try:
                receipt=self._receipt(name,fingerprint_of(item))
                seen=await self.history.hass.async_add_executor_job(self.history.app_archive.relay_seen,receipt)
                if not seen:continue
                # Both path parts are regex-validated, so no traversal is possible.
                # Both path parts are regex-validated, so no traversal is possible.
                await self.auth_request('DELETE',FILES_API,{'path':'disk:'+self.folder+'/'+name})
            except DiskThrottled:
                self.cleanup_error='throttled';return
            except DiskUnauthorized:
                # A token without write scope is a configuration problem, not a blip.
                self.cleanup_blocked=True;self.cleanup_error='unauthorized';return
            except Exception:
                self.cleanup_error='failed';continue
            self.cleanup_deleted+=1

    def _set_status(self,*,failed=False,unreachable=False):
        if unreachable:base='проверьте связь, публичную папку, ID и ключ'
        elif failed:base='часть файлов не прочитана, проверьте ID и ключ'
        elif self.offset:base='продолжается загрузка истории'
        else:base='синхронизировано'
        note=''
        if self.cleanup_wanted:
            if self.cleanup_error=='unauthorized':note='; очистка недоступна: проверьте OAuth-токен'
            elif self.cleanup_error=='throttled':note='; очистка ждёт разрешения частоты запросов'
            elif self.cleanup_error=='failed':note='; часть файлов не удалена'
            if self.cleanup_deleted:note+=f'; в корзину перемещено: {self.cleanup_deleted}'
        self.status='Яндекс.Диск: '+base+note

    async def poll(self):
        if self.closed or self.lock.locked():return
        # A short interval must not become a hammer: after a 429 the whole folder
        # scan waits, not just the deletion pass.
        if self.throttle_until and time.time() < self.throttle_until:
            return
        async with self.lock:
            self.cleanup_deleted=0
            try:
                async with asyncio.timeout(25):
                    failed=False
                    latest=await self.meta('/latest-'+self.vehicle+'.jloc')
                    if latest:
                        try:await self.import_file(latest)
                        except (DiskThrottled,DiskUnauthorized):raise
                        except Exception:failed=True
                    page=await self.meta(limit=500,offset=self.offset,sort='name')
                    if not page or page.get('type')!='dir':raise ValueError('A public folder is required')
                    embedded=page.get('_embedded',{})
                    items=embedded.get('items',[])
                    imported=0
                    for item in items:
                        # A rate limit or a token problem ends the cycle instead of
                        # being counted as one unreadable file.
                        try:imported+=bool(await self.import_file(item))
                        except (DiskThrottled,DiskUnauthorized):raise
                        except Exception:failed=True
                        self.offset+=1
                        if imported>=10:break
                    if not items or self.offset>=int(embedded.get('total',self.offset)):
                        self.offset=0
                    await self.cleanup(items)
                    # A clean cycle clears the backoff; a throttled one keeps it.
                    if self.cleanup_error!='throttled':
                        self.throttle_ms=0;self.throttle_until=0.0
                    self._set_status(failed=failed)
            except DiskThrottled:
                self._set_status(unreachable=True)
            except Exception:
                # Never log public URLs, signed download URLs, keys or coordinates.
                self._set_status(unreachable=True)
