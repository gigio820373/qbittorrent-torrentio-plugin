# VERSION: 3.09
# AUTHORS: gigio820373
# LICENSING INFORMATION: GPL v3
# DESCRIZIONE: Torrentio Ultra ITA — v3.09
#              FIX: risolto bug che taggava falsi [ITA] (es. file con solo SUB.ITA).
#              TRUST_LANGUAGE_FILTER ora è False di default.
#              + CONFIGURAZIONE AUTOMATICA + PERSISTENZA STATO (v3.08).

import sys

if sys.version_info < (3, 8):
    raise RuntimeError(
        "Torrentio Ultra ITA richiede Python 3.8 o superiore "
        "(rilevato {}.{}). Aggiorna Python o usa una build di qBittorrent "
        "con Python piu' recente.".format(*sys.version_info[:2])
    )

import concurrent.futures
import datetime
import json
import os
import random
import re
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from novaprinter import prettyPrinter


RE_BTIH_HEX = re.compile(r'^[0-9a-fA-F]{40}$')
RE_BTIH_BASE32 = re.compile(r'^[A-Z2-7a-z2-7]{32}$')


def _validate_info_hash(info_hash):
    if not info_hash or not isinstance(info_hash, str):
        return None
    h = info_hash.strip()
    if RE_BTIH_HEX.match(h):
        return h.lower()
    if RE_BTIH_BASE32.match(h):
        return h
    return None


def _validate_magnet(magnet):
    if not magnet or not isinstance(magnet, str):
        return None
    m = magnet.strip()
    if not m.startswith('magnet:?xt=urn:btih:'):
        return None
    try:
        rest = m[len('magnet:?xt=urn:btih:'):]
        hash_part = rest.split('&', 1)[0]
    except Exception:
        return None
    if not _validate_info_hash(hash_part):
        return None
    return m


# ----------------------------------------------------------------------
# Configurazione persistente — torrentio.json accanto al plugin
# ----------------------------------------------------------------------

CONFIGURABLE_KEYS = {
    'DEBUG', 'ONLY_ITA', 'ONLY_ITA_AUDIO', 'USE_ITA_FLAG', 'TRUST_LANGUAGE_FILTER',
    'PROVIDERS', 'QUALITY_FILTER', 'TORRENTIO_SORT', 'LIMIT',
    'USE_KITSU_FOR_ANIME', 'MAX_TITLES', 'MAX_WORKERS', 'QUERY_FALLBACKS',
    'HTTP_TIMEOUT', 'HTTP_RETRIES',
    'RATE_LIMIT_ENABLED', 'RATE_LIMIT_INTERVAL', 'RATE_LIMIT_ADAPTIVE',
    'SELF_HEALING_ENABLED', 'HEALTH_FAIL_THRESHOLD', 'HEALTH_COOLDOWN', 'FALLBACK_ON_BLOCK',
    'USE_PROXY_ON_BLOCK', 'PROXY_TIMEOUT',
    'CACHE_ENABLED', 'CACHE_TTL_IMDB', 'CACHE_TTL_STREAM',
    'GLOBAL_TIMEOUT', 'SMART_DEDUP',
    'SEARCH_ALL_SEASONS', 'MAX_SEASONS',
    'SHOW_RELEASE_SUFFIX', 'SHOW_TRACKER_IN_NAME', 'SHOW_AUDIO_INFO',
    'SORT_STRATEGY', 'MIN_SEEDS_FOR_PRIORITY',
    'MIN_RESOLUTION', 'STRICT_RESOLUTION',
    'IMDB_CB_FAIL_THRESHOLD', 'IMDB_CB_RECOVERY_TIMEOUT',
}


def _plugin_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def _state_dir():
    try:
        return tempfile.gettempdir()
    except Exception:
        return _plugin_dir()


def _atomic_write_json(path, data):
    try:
        d = os.path.dirname(path) or '.'
        if not os.path.isdir(d):
            return False
        fd, tmp = tempfile.mkstemp(prefix='.torrentio_', suffix='.tmp', dir=d)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            os.replace(tmp, path)
            return True
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            return False
    except Exception:
        return False


class _RateLimiter(object):
    def __init__(self, interval, max_interval=5.0):
        self.interval = interval
        self.max_interval = max_interval
        self._current = interval
        self._lock = threading.Lock()
        self._last = 0.0

    @property
    def current(self):
        with self._lock:
            return self._current

    def wait(self):
        with self._lock:
            now = time.time()
            delta = now - self._last
            if delta < self._current:
                time.sleep(self._current - delta)
            self._last = time.time()

    def escalate(self):
        with self._lock:
            self._current = min(self._current * 1.5, self.max_interval)

    def relax(self):
        with self._lock:
            self._current = max(self.interval, self._current * 0.9)

    def to_dict(self):
        with self._lock:
            return {'current': self._current}

    def load_dict(self, data):
        try:
            c = float(data.get('current', self.interval))
            with self._lock:
                self._current = max(self.interval, min(c, self.max_interval))
        except (TypeError, ValueError):
            pass


class _TTLCache(object):
    def __init__(self, ttl):
        self.ttl = ttl
        self._lock = threading.Lock()
        self._store = {}

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key, value):
        with self._lock:
            self._store[key] = (value, time.time() + self.ttl)
            if len(self._store) > 500:
                now = time.time()
                self._store = {k: v for k, v in self._store.items() if v[1] > now}

    def clear(self):
        with self._lock:
            self._store.clear()

    def to_dict(self):
        with self._lock:
            now = time.time()
            items = []
            for k, (v, exp) in self._store.items():
                if exp > now:
                    items.append({'k': list(k) if isinstance(k, tuple) else k,
                                  'v': v, 'exp': exp})
            return {'items': items, 'ttl': self.ttl}

    def load_dict(self, data):
        try:
            items = data.get('items', [])
            now = time.time()
            with self._lock:
                for it in items:
                    k = it.get('k')
                    if isinstance(k, list):
                        k = tuple(k)
                    v = it.get('v')
                    exp = float(it.get('exp', 0))
                    if exp > now and k is not None:
                        self._store[k] = (v, exp)
        except Exception:
            pass


class _InstanceHealth(object):
    def __init__(self, fail_threshold=2, cooldown=120):
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self._lock = threading.Lock()
        self._state = {}

    def is_healthy(self, url):
        with self._lock:
            state = self._state.get(url)
            if state is None:
                return True
            return state.get('blocked_until', 0) <= time.time()

    def record_success(self, url):
        with self._lock:
            self._state.pop(url, None)

    def record_failure(self, url, error_type):
        with self._lock:
            now = time.time()
            state = self._state.setdefault(url, {'fails': 0, 'blocked_until': 0, 'last_error': None})
            if state['blocked_until'] > 0 and state['blocked_until'] <= now:
                state['fails'] = 0
                state['blocked_until'] = 0
            state['fails'] += 1
            state['last_error'] = error_type
            if error_type == 'blocked':
                state['blocked_until'] = now + self.cooldown * 3
            elif state['fails'] >= self.fail_threshold:
                state['blocked_until'] = now + self.cooldown

    def get_ordered_instances(self, instances):
        with self._lock:
            now = time.time()
            healthy, recovering = [], []
            for url in instances:
                state = self._state.get(url)
                if state is None or state.get('blocked_until', 0) <= now:
                    healthy.append(url)
                else:
                    recovering.append((url, state.get('blocked_until', 0)))
            recovering.sort(key=lambda x: x[1])
            return healthy + [u for u, _ in recovering]

    def to_dict(self):
        with self._lock:
            return {'state': {u: dict(s) for u, s in self._state.items()}}

    def load_dict(self, data):
        try:
            st = data.get('state', {})
            if isinstance(st, dict):
                with self._lock:
                    self._state = {u: dict(v) for u, v in st.items() if isinstance(v, dict)}
        except Exception:
            pass


class _CircuitBreaker(object):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, fail_threshold=5, recovery_timeout=60.0):
        self.fail_threshold = fail_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_taken = False
        self._lock = threading.Lock()

    @property
    def state(self):
        with self._lock:
            return self._state

    def allow_request(self):
        with self._lock:
            now = time.time()
            if self._state == self.OPEN:
                if now - self._opened_at >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_taken = True
                    return True
                return False
            if self._state == self.HALF_OPEN:
                if self._half_open_taken:
                    return False
                self._half_open_taken = True
                return True
            return True

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._state = self.CLOSED
            self._half_open_taken = False

    def record_failure(self):
        with self._lock:
            self._failures += 1
            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                self._opened_at = time.time()
                self._half_open_taken = False
            elif self._failures >= self.fail_threshold:
                self._state = self.OPEN
                self._opened_at = time.time()

    def to_dict(self):
        with self._lock:
            return {
                'state': self._state,
                'failures': self._failures,
                'opened_at': self._opened_at,
                'half_open_taken': self._half_open_taken,
            }

    def load_dict(self, data):
        try:
            with self._lock:
                self._state = data.get('state', self.CLOSED)
                self._failures = int(data.get('failures', 0))
                self._opened_at = float(data.get('opened_at', 0))
                self._half_open_taken = bool(data.get('half_open_taken', False))
                if self._state not in (self.CLOSED, self.OPEN, self.HALF_OPEN):
                    self._state = self.CLOSED
        except Exception:
            pass


@dataclass(frozen=True)
class ParsedStream:
    first_line: str
    quality: str
    tracker: str
    is_ita: bool
    is_multi: bool
    is_sub: bool
    is_pack: bool
    codec: str
    audio: str
    resolution: str
    size_bytes: str
    seeds: str


class _TorrentioClient(object):
    def __init__(self, http_json, base_url_builder, logger,
                 health_tracker=None, proxy_urls=None,
                 use_proxy_on_block=True, proxy_timeout=8,
                 fallback_on_block=True):
        self._http_json = http_json
        self._base_url_builder = base_url_builder
        self._logger = logger or (lambda msg: None)
        self._health = health_tracker
        self._proxy_urls = list(proxy_urls or [])
        self._use_proxy_on_block = use_proxy_on_block
        self._proxy_timeout = proxy_timeout
        self._fallback_on_block = fallback_on_block

    def fetch_stream(self, instances, path):
        ordered = (
            self._health.get_ordered_instances(instances)
            if self._health is not None else list(instances)
        )
        last_error = 'all_failed'
        for base in ordered:
            streams, error = self._try_instance(base, path)
            if error is None:
                if self._health is not None:
                    self._health.record_success(base)
                return streams, None
            if self._health is not None:
                self._health.record_failure(base, error)
            last_error = error
            self._logger('istanza {} in errore ({}), passo alla successiva'.format(base, error))
        return [], last_error

    def _apply_proxy(self, url, template):
        if not template:
            return url
        if '{rawUrl}' in template:
            return template.replace('{rawUrl}', url)
        if '{url}' in template:
            return template.replace('{url}', urllib.parse.quote(url, safe=''))
        return template.rstrip('/') + '/' + urllib.parse.quote(url, safe='')

    def _try_proxies(self, target_url):
        if not self._proxy_urls or not self._use_proxy_on_block:
            return None, 'blocked'
        for template in self._proxy_urls:
            proxy_url = self._apply_proxy(target_url, template)
            data, error = self._http_json(
                proxy_url, timeout=self._proxy_timeout, retries=0, throttle=False
            )
            if error is None:
                streams = data.get('streams') if isinstance(data, dict) else None
                if isinstance(streams, list):
                    return streams, None
        return None, 'blocked'

    def _should_try_clean_url(self, error):
        if not error:
            return False
        if error == 'invalid_json':
            return True
        if error.startswith('http_4'):
            return True
        return False

    def _try_instance(self, base, path):
        url = '{}/stream/{}.json'.format(self._base_url_builder(base), path)
        data, error = self._http_json(url, throttle=True)
        if error is None:
            streams = data.get('streams') if isinstance(data, dict) else None
            return (streams if isinstance(streams, list) else []), None

        if error == 'blocked':
            streams, proxy_error = self._try_proxies(url)
            if proxy_error is None:
                return streams, None
            return None, 'blocked'

        if error == 'ratelimit':
            return None, error

        if self._fallback_on_block and self._should_try_clean_url(error):
            fallback_url = '{}/stream/{}.json'.format(base.rstrip('/'), path)
            data2, error2 = self._http_json(fallback_url, throttle=True)
            if error2 is None:
                streams = data2.get('streams') if isinstance(data2, dict) else None
                return (streams if isinstance(streams, list) else []), None
            if error2 == 'blocked':
                streams, proxy_error = self._try_proxies(fallback_url)
                if proxy_error is None:
                    return streams, None
            return None, error2

        return None, error


class torrentio(object):
    url = 'https://torrentio.strem.fun'
    name = 'Torrentio Ultra ITA'

    supported_categories = {
        'all': 'all',
        'movies': 'movie',
        'tv': 'series',
        'anime': 'anime'
    }

    # --- Persistenza e configurazione automatica ---
    CONFIG_ENABLED = True
    CONFIG_FILENAME = 'torrentio.json'
    PERSIST_STATE = True
    STATE_FILENAME = 'torrentio_state.json'

    DEBUG = False
    ONLY_ITA = False
    ONLY_ITA_AUDIO = False
    USE_ITA_FLAG = True
    
    # FIX v3.09: Ora è False di default per non fidarsi ciecamente di Torrentio
    TRUST_LANGUAGE_FILTER = False

    TORRENTIO_INSTANCES = [
        'https://torrentio.strem.fun',
        'https://torrentio.elfhosted.com',
    ]

    PROVIDERS = (
        "yts,eztv,1337x,thepiratebay,kickasstorrents,"
        "torrentgalaxy,ilcorsaronero,magnetdl,nyaasi"
    )

    QUALITY_FILTER = '480p,other,scr,cam'
    TORRENTIO_SORT = 'qualitysize'
    LIMIT = ''

    USE_KITSU_FOR_ANIME = False

    MAX_TITLES = 8
    MAX_WORKERS = 4
    QUERY_FALLBACKS = 2
    HTTP_TIMEOUT = 10
    HTTP_RETRIES = 2

    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_INTERVAL = 1.0
    RATE_LIMIT_ADAPTIVE = True

    SELF_HEALING_ENABLED = True
    HEALTH_FAIL_THRESHOLD = 2
    HEALTH_COOLDOWN = 120
    FALLBACK_ON_BLOCK = True

    PROXY_URLS = [
        'https://api.allorigins.win/raw?url={url}',
        'https://api.codetabs.com/v1/proxy?quest={url}',
        'https://api.cors.lol/?url={url}',
        'https://cors.eu.org/{rawUrl}',
        'https://cors.x2u.in/{rawUrl}',
        'https://corsproxy.io/?url={url}',
    ]
    USE_PROXY_ON_BLOCK = True
    PROXY_TIMEOUT = 8

    CACHE_ENABLED = True
    CACHE_TTL_IMDB = 3600
    CACHE_TTL_STREAM = 300

    GLOBAL_TIMEOUT = 90
    SMART_DEDUP = True

    SEARCH_ALL_SEASONS = False
    MAX_SEASONS = 10

    SHOW_RELEASE_SUFFIX = False
    SHOW_TRACKER_IN_NAME = False
    SHOW_AUDIO_INFO = True

    SORT_STRATEGY = 'ita_then_size'
    MIN_SEEDS_FOR_PRIORITY = 0

    MIN_RESOLUTION = '1080p'
    STRICT_RESOLUTION = False
    RESOLUTION_PRIORITY = ['4k', '1440p', '1080p', '720p', '480p', '360p', 'unknown']

    IMDB_CB_FAIL_THRESHOLD = 5
    IMDB_CB_RECOVERY_TIMEOUT = 60.0

    USER_AGENTS = [
        ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
        ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'),
        ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
         'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'),
        ('Mozilla/5.0 (X11; Linux x86_64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
        ('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
         'Gecko/20100101 Firefox/125.0'),
    ]

    FALLBACK_TRACKERS = [
        'udp://tracker.opentrackr.org:1337/announce',
        'udp://open.stealth.si:80/announce',
        'udp://tracker.torrent.eu.org:451/announce',
        'udp://exodus.desync.com:6969/announce',
        'udp://opentracker.i2p.rocks:6969/announce'
    ]

    RETRY_CODES = (429, 500, 502, 503, 504)
    MOVIE_TYPES = {'movie', 'tvMovie', 'video'}
    SERIES_TYPES = {'tvSeries', 'tvMiniSeries'}
    FLAG_IT = '\U0001F1EE\U0001F1F9'
    SIZE_UNITS = {'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3, 'T': 1024 ** 4}

    RE_SE_FULL = re.compile(
        r'\b(?:s|stagione\s*|season\s*)(\d{1,2})\s*(?:e|ep|episode\s*|episodio\s*|x)(\d{1,4})\b',
        re.IGNORECASE
    )
    RE_SE_ALT = re.compile(r'\b(\d{1,2})x(\d{1,4})\b', re.IGNORECASE)
    RE_S_ONLY = re.compile(r'\b(?:s|stagione\s*|season\s*)(\d{1,2})\b', re.IGNORECASE)
    RE_IMDB_ID = re.compile(r'^(tt\d{7,8})$', re.IGNORECASE)
    RE_YEAR_END = re.compile(r'\(?\b((?:19|20)\d{2})\b\)?\s*$')
    RE_TOKEN_ITA = re.compile(r'\b(?:ita|italian|italiano)\b', re.IGNORECASE)
    RE_TOKEN_PACK = re.compile(r'\bpack\b', re.IGNORECASE)
    RES_TOKENS = {
        '4k': re.compile(r'\b(?:4k|2160p|uhd)\b', re.IGNORECASE),
        '1080p': re.compile(r'\b1080p\b', re.IGNORECASE),
        '720p': re.compile(r'\b720p\b', re.IGNORECASE),
        '480p': re.compile(r'\b480p\b', re.IGNORECASE),
    }
    RE_EP_TAG = re.compile(r'\bs\d{1,2}[\s._-]?e\d{1,3}\b|\b\d{1,2}x\d{2,3}\b', re.IGNORECASE)
    RE_SUB_ITA = re.compile(r'\b(?:sub[\s._-]?ita|vost[\s._-]?ita)\b', re.IGNORECASE)
    RE_AUDIO_ITA = re.compile(r'\b(?:ita|italian)\b', re.IGNORECASE)
    RE_NON_ITA_LANG = re.compile(
        r'\b(?:eng|english|fra|french|deu|german|spa|spanish|jpn|japanese|rus|russian)\b',
        re.IGNORECASE
    )
    RE_PREMIUM_AUDIO = re.compile(
        r'\btruehd\b|\bdts[\s._-]?hd[\s._-]?ma\b|\bdts[\s._-]?hd\b|\batmos\b',
        re.IGNORECASE
    )
    RE_TRACKER = re.compile(r'\u2699\ufe0f?\s*([^\n\r]+)')
    RE_SEEDS = re.compile(r'\U0001F464\s*(\d+)')
    RE_SIZE = re.compile(r'\U0001F4BE\s*([\d.]+)\s*([KMGT])i?B', re.IGNORECASE)

    RE_CODEC = re.compile(r'\b(h[\s._-]?265|hevc|x265|h[\s._-]?264|x264|av1)\b', re.IGNORECASE)
    RE_RESOLUTION = re.compile(
        r'\b(2160p|4k|uhd|1440p|2k|1080p|720p|480p|360p)\b',
        re.IGNORECASE
    )

    RE_DEDUP_STRIP = re.compile(
        r'\b(?:ita|italian|italiano|sub[\s._-]?ita|multi|dual[\s._-]?audio|'
        r'4k|2160p|uhd|1080p|720p|480p|hdr|sdr|'
        r'h[\s._-]?26[45]|hevc|x26[45]|av1|'
        r'aac|e?ac3|dts|truehd|atmos|ddp?\d|'
        r'bluray|bdrip|web[\s._-]?dl|webrip|hdrip|dvdrip|remux)\b',
        re.IGNORECASE
    )

    _shared_lock = threading.Lock()
    _health_shared = None
    _rate_limiter_shared = None
    _imdb_cache = None
    _stream_cache = None
    _imdb_circuit_breaker = None
    _state_lock = threading.Lock()

    def __init__(self):
        if not self.TORRENTIO_INSTANCES:
            raise ValueError('TORRENTIO_INSTANCES non puo\' essere vuota')

        if self.CONFIG_ENABLED:
            self._auto_load_config()

        self._health_tracker = self._get_or_create_health() if self.SELF_HEALING_ENABLED else None
        self._rate_limiter = self._get_or_create_rate_limiter() if self.RATE_LIMIT_ENABLED else None
        self._imdb_cb = self._get_or_create_imdb_circuit_breaker()
        self._init_caches()

        if self.PERSIST_STATE:
            self._auto_load_state()

    def _config_path(self):
        return os.path.join(_plugin_dir(), self.CONFIG_FILENAME)

    def _auto_load_config(self):
        path = self._config_path()
        if not os.path.isfile(path):
            try:
                defaults = {k: getattr(type(self), k) for k in CONFIGURABLE_KEYS
                            if hasattr(type(self), k)}
                payload = {
                    '_comment': (
                        'Configurazione Torrentio Ultra ITA. '
                        'Modifica i valori qui sotto: sovrascrivono i default '
                        'del plugin e NON vengono toccati dagli aggiornamenti.'
                    ),
                    '_documentazione': (
                        'https://github.com/gigio820373/qbittorrent-torrentio-plugin'
                    ),
                }
                payload.update(defaults)
                _atomic_write_json(path, payload)
            except Exception:
                pass
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if key not in CONFIGURABLE_KEYS:
                continue
            try:
                setattr(type(self), key, value)
            except Exception:
                pass

    def _state_path(self):
        return os.path.join(_state_dir(), self.STATE_FILENAME)

    def _auto_load_state(self):
        path = self._state_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        try:
            if self._rate_limiter is not None and 'rate_limiter' in data:
                self._rate_limiter.load_dict(data['rate_limiter'])
            if self._imdb_cache is not None and 'imdb_cache' in data:
                self._imdb_cache.load_dict(data['imdb_cache'])
            if self._stream_cache is not None and 'stream_cache' in data:
                self._stream_cache.load_dict(data['stream_cache'])
            if self._health_tracker is not None and 'health' in data:
                self._health_tracker.load_dict(data['health'])
            if self._imdb_cb is not None and 'imdb_cb' in data:
                self._imdb_cb.load_dict(data['imdb_cb'])
        except Exception:
            pass

    def _auto_save_state(self):
        if not self.PERSIST_STATE:
            return
        try:
            data = {}
            if self._rate_limiter is not None:
                data['rate_limiter'] = self._rate_limiter.to_dict()
            if self._imdb_cache is not None:
                data['imdb_cache'] = self._imdb_cache.to_dict()
            if self._stream_cache is not None:
                data['stream_cache'] = self._stream_cache.to_dict()
            if self._health_tracker is not None:
                data['health'] = self._health_tracker.to_dict()
            if self._imdb_cb is not None:
                data['imdb_cb'] = self._imdb_cb.to_dict()
            data['_saved_at'] = time.time()
            data['_pid'] = os.getpid()
            _atomic_write_json(self._state_path(), data)
        except Exception:
            pass

    @classmethod
    def _get_or_create_health(cls):
        with cls._shared_lock:
            if cls._health_shared is None:
                cls._health_shared = _InstanceHealth(
                    fail_threshold=cls.HEALTH_FAIL_THRESHOLD,
                    cooldown=cls.HEALTH_COOLDOWN
                )
            return cls._health_shared

    @classmethod
    def _get_or_create_rate_limiter(cls):
        with cls._shared_lock:
            if cls._rate_limiter_shared is None:
                cls._rate_limiter_shared = _RateLimiter(cls.RATE_LIMIT_INTERVAL)
            return cls._rate_limiter_shared

    @classmethod
    def _get_or_create_imdb_circuit_breaker(cls):
        with cls._shared_lock:
            if cls._imdb_circuit_breaker is None:
                cls._imdb_circuit_breaker = _CircuitBreaker(
                    fail_threshold=cls.IMDB_CB_FAIL_THRESHOLD,
                    recovery_timeout=cls.IMDB_CB_RECOVERY_TIMEOUT
                )
            return cls._imdb_circuit_breaker

    @classmethod
    def _init_caches(cls):
        with cls._shared_lock:
            if cls._imdb_cache is None and cls.CACHE_ENABLED:
                cls._imdb_cache = _TTLCache(cls.CACHE_TTL_IMDB)
            if cls._stream_cache is None and cls.CACHE_ENABLED:
                cls._stream_cache = _TTLCache(cls.CACHE_TTL_STREAM)

    def _build_base_url(self, base):
        options = []
        if self.PROVIDERS:
            options.append('providers=' + self.PROVIDERS.replace(' ', ''))
        options.append('language=italian')
        if self.QUALITY_FILTER:
            options.append('qualityfilter=' + self.QUALITY_FILTER.replace(' ', ''))
        if self.TORRENTIO_SORT:
            options.append('sort=' + self.TORRENTIO_SORT.replace(' ', ''))
        if self.LIMIT:
            options.append('limit=' + str(self.LIMIT))
        return base.rstrip('/') + '/' + '%7C'.join(options)

    def _get_headers(self):
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def _log(self, msg):
        if not self.DEBUG:
            return
        try:
            path = os.path.join(tempfile.gettempdir(), 'torrentio_ultra.log')
            with open(path, 'a', encoding='utf-8') as f:
                f.write('pid={} {}'.format(os.getpid(), time.strftime('%H:%M:%S ')) + msg + '\n')
        except OSError:
            pass

    def _http_json(self, url, headers=None, timeout=None, retries=None, throttle=False):
        timeout = timeout or self.HTTP_TIMEOUT
        retries = self.HTTP_RETRIES if retries is None else retries
        hdrs = self._get_headers()
        if headers:
            hdrs.update(headers)

        for attempt in range(retries + 1):
            if throttle and self._rate_limiter is not None:
                self._rate_limiter.wait()
            try:
                req = urllib.request.Request(url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode('utf-8')), None
            except urllib.error.HTTPError as exc:
                self._log('HTTP {} su {}'.format(exc.code, url))
                if exc.code == 403:
                    return None, 'blocked'
                if exc.code == 429:
                    if attempt < retries:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    return None, 'ratelimit'
                if exc.code in self.RETRY_CODES and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if 500 <= exc.code < 600:
                    return None, 'server'
                return None, 'http_{}'.format(exc.code)
            except ValueError as exc:
                self._log('JSON non valido da {}: {}'.format(url, exc))
                return None, 'invalid_json'
            except Exception as exc:
                self._log('errore su {}: {}'.format(url, exc))
                msg = str(exc).lower()
                err = 'timeout' if ('timed out' in msg or 'timeout' in msg) else 'network'
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None, err
        return None, 'unknown'

    def _extract_season_episode(self, query):
        match = self.RE_SE_FULL.search(query)
        if match:
            clean = self.RE_SE_FULL.sub('', query).strip()
            return int(match.group(1)), int(match.group(2)), clean
        match_alt = self.RE_SE_ALT.search(query)
        if match_alt:
            clean = self.RE_SE_ALT.sub('', query).strip()
            return int(match_alt.group(1)), int(match_alt.group(2)), clean
        match_s = self.RE_S_ONLY.search(query)
        if match_s:
            clean = self.RE_S_ONLY.sub('', query).strip()
            return int(match_s.group(1)), None, clean
        return None, None, query.strip()

    def _extract_filters(self, query):
        filters = {'ita': False, 'pack': False, 'res': None}
        q = query
        if self.RE_TOKEN_ITA.search(q):
            filters['ita'] = True
            q = self.RE_TOKEN_ITA.sub(' ', q)
        if self.RE_TOKEN_PACK.search(q):
            filters['pack'] = True
            q = self.RE_TOKEN_PACK.sub(' ', q)
        for key, rx in self.RES_TOKENS.items():
            if rx.search(q):
                filters['res'] = key
                q = rx.sub(' ', q)
                break
        q = ' '.join(q.split())
        if not q:
            return query, {'ita': False, 'pack': False, 'res': None}
        return q, filters

    def _extract_year(self, query):
        match = self.RE_YEAR_END.search(query)
        if not match:
            return None, query
        year = match.group(1)
        if int(year) > datetime.date.today().year + 1:
            return None, query
        clean = ' '.join(query[:match.start()].split())
        if not clean:
            return None, query
        return year, clean

    def _normalize_slug(self, text):
        normalized = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        return re.sub(r'[^a-z0-9_]+', '_', normalized.lower()).strip('_')

    def _make_item(self, ref, title, year, is_series, path_type, desc_link):
        return {
            'id': ref,
            'title': title,
            'year': str(year) if year else '',
            'is_series': is_series,
            'path_type': path_type,
            'desc_link': desc_link
        }

    def _search_imdb(self, query, kinds):
        cache_key = None
        if self.CACHE_ENABLED and self._imdb_cache is not None:
            cache_key = ('imdb', self._normalize_slug(query) or query, tuple(sorted(kinds)))
            cached = self._imdb_cache.get(cache_key)
            if cached is not None:
                return list(cached)
        result, error = self._search_imdb_uncached(query, kinds)
        if cache_key and result is not None and error is None:
            self._imdb_cache.set(cache_key, list(result))
        return result

    def _search_imdb_uncached(self, query, kinds):
        imdb_match = self.RE_IMDB_ID.match(query)
        if imdb_match:
            imdb_id = imdb_match.group(1).lower()
            link = 'https://www.imdb.com/title/{}/'.format(imdb_id)
            items = []
            for kind in ('movie', 'series'):
                if kind in kinds:
                    items.append(self._make_item(imdb_id, imdb_id, '', kind == 'series', kind, link))
            return items, None

        if not self._imdb_cb.allow_request():
            return [], 'circuit_open'

        slug = self._normalize_slug(query)
        if not slug:
            return [], None
        imdb_url = 'https://v3.sg.media-imdb.com/suggestion/{}/{}.json'.format(slug[0], slug)
        data, error = self._http_json(imdb_url, timeout=8, retries=1)

        if error in ('server', 'timeout', 'network', 'ratelimit'):
            self._imdb_cb.record_failure()
            return [], error
        if error is not None:
            return [], error
        self._imdb_cb.record_success()

        if not isinstance(data, dict):
            return [], 'invalid_response'

        items = []
        for entry in data.get('d', []):
            imdb_id = entry.get('id', '')
            if not imdb_id.startswith('tt'):
                continue
            item_type = entry.get('qid', '')
            if item_type in self.MOVIE_TYPES:
                kind = 'movie'
            elif item_type in self.SERIES_TYPES:
                kind = 'series'
            else:
                continue
            if kind not in kinds:
                continue
            items.append(self._make_item(
                imdb_id, entry.get('l', 'Sconosciuto'), entry.get('y', ''),
                kind == 'series', kind, 'https://www.imdb.com/title/{}/'.format(imdb_id)
            ))
        return items, None

    def _search_kitsu(self, query, kinds):
        params = urllib.parse.urlencode({'filter[text]': query, 'page[limit]': 5})
        data, _ = self._http_json(
            'https://kitsu.io/api/edge/anime?' + params,
            headers={'Accept': 'application/vnd.api+json'},
            timeout=8, retries=1
        )
        if not isinstance(data, dict):
            return []
        items = []
        for entry in data.get('data', []):
            kid = entry.get('id')
            attrs = entry.get('attributes') or {}
            if not kid:
                continue
            kind = 'movie' if str(attrs.get('subtype', '')).lower() == 'movie' else 'series'
            if kind not in kinds:
                continue
            title = attrs.get('canonicalTitle') or (attrs.get('titles') or {}).get('en_jp') or 'Sconosciuto'
            year = str(attrs.get('startDate') or '')[:4]
            items.append(self._make_item(
                'kitsu:{}'.format(kid), title, year, kind == 'series', 'anime',
                'https://kitsu.io/anime/{}'.format(kid)
            ))
        return items

    def _query_candidates(self, clean_query, full_query):
        candidates = [clean_query]
        if full_query != clean_query:
            candidates.append(full_query)
        words = clean_query.split()
        for drop in range(1, self.QUERY_FALLBACKS + 1):
            if len(words) > drop:
                candidates.append(' '.join(words[:-drop]))
        seen, unique = set(), []
        for cand in candidates:
            key = self._normalize_slug(cand) or cand
            if key not in seen:
                seen.add(key)
                unique.append(cand)
        return unique

    def _lookup(self, finder, candidates, kinds, year):
        for cand in candidates:
            items = finder(cand, kinds)
            if items:
                if year:
                    items.sort(key=lambda it: it['year'] != year)
                return items[:self.MAX_TITLES]
        return []

    def _find_titles(self, clean_query, full_query, cat, kinds, year):
        if self.RE_IMDB_ID.match(clean_query):
            candidates = [clean_query]
            finders = [self._search_imdb]
        else:
            candidates = self._query_candidates(clean_query, full_query)
            finders = []
            if cat == 'anime' and self.USE_KITSU_FOR_ANIME:
                finders.append(self._search_kitsu)
            finders.append(self._search_imdb)
        for finder in finders:
            items = self._lookup(finder, candidates, kinds, year)
            if items:
                return items
        return []

    def _make_request(self, item, season, episode):
        if not item['is_series']:
            return [{
                'item': item,
                'path': '{}/{}'.format(item['path_type'], item['id']),
                'label': '',
                'season_only': False
            }]

        if item['id'].startswith('kitsu:'):
            ep = episode if episode is not None else 1
            return [{
                'item': item,
                'path': '{}/{}:{}'.format(item['path_type'], item['id'], ep),
                'label': ' E{:02d}'.format(ep),
                'season_only': False
            }]

        if season is not None:
            eff_episode = episode if episode is not None else 1
            season_only = episode is None
            label = ' S{:02d}'.format(season) if season_only else ' S{:02d}E{:02d}'.format(season, eff_episode)
            return [{
                'item': item,
                'path': '{}/{}:{}:{}'.format(item['path_type'], item['id'], season, eff_episode),
                'label': label,
                'season_only': season_only
            }]

        if not self.SEARCH_ALL_SEASONS:
            return [{
                'item': item,
                'path': '{}/{}:1:1'.format(item['path_type'], item['id']),
                'label': ' S01E01',
                'season_only': False
            }]

        requests = []
        for s in range(1, self.MAX_SEASONS + 1):
            requests.append({
                'item': item,
                'path': '{}/{}:{}:1'.format(item['path_type'], item['id'], s),
                'label': ' S{:02d}'.format(s),
                'season_only': True
            })
        return requests

    def _get_torrentio_client(self):
        return _TorrentioClient(
            http_json=self._http_json,
            base_url_builder=self._build_base_url,
            logger=self._log,
            health_tracker=self._health_tracker,
            proxy_urls=self.PROXY_URLS,
            use_proxy_on_block=self.USE_PROXY_ON_BLOCK,
            proxy_timeout=self.PROXY_TIMEOUT,
            fallback_on_block=self.FALLBACK_ON_BLOCK,
        )

    def _fetch_stream(self, req):
        path = req['path']

        if self.CACHE_ENABLED and self._stream_cache is not None:
            cached = self._stream_cache.get(path)
            if cached is not None:
                return req, list(cached)

        client = self._get_torrentio_client()
        streams, error = client.fetch_stream(self.TORRENTIO_INSTANCES, path)

        if error is None:
            if self._rate_limiter is not None and self.RATE_LIMIT_ADAPTIVE:
                self._rate_limiter.relax()
            if self.CACHE_ENABLED and self._stream_cache is not None and streams:
                self._stream_cache.set(path, list(streams))
        elif error == 'ratelimit' and self._rate_limiter is not None and self.RATE_LIMIT_ADAPTIVE:
            self._rate_limiter.escalate()

        return req, streams

    def _build_magnet(self, stream, display_name):
        existing = stream.get('magnet')
        if existing:
            validated = _validate_magnet(existing)
            if validated:
                return validated
            self._log('magnet scartato (schema o hash non validi)')
            return None

        info_hash = stream.get('infoHash')
        validated_hash = _validate_info_hash(info_hash)
        if not validated_hash:
            if info_hash:
                self._log('infoHash scartato: {!r}'.format(info_hash))
            return None

        trackers = []
        for src in stream.get('sources') or []:
            if isinstance(src, str) and src.startswith('tracker:'):
                tr = src[8:]
                if tr and tr not in trackers:
                    trackers.append(tr)
        for fb in self.FALLBACK_TRACKERS:
            if fb not in trackers:
                trackers.append(fb)

        encoded_name = urllib.parse.quote(display_name)
        tr_params = ''.join('&tr={}'.format(urllib.parse.quote(tr)) for tr in trackers[:15])
        return 'magnet:?xt=urn:btih:{}&dn={}{}'.format(validated_hash, encoded_name, tr_params)

    def _parse_size(self, text):
        match = self.RE_SIZE.search(text)
        if not match:
            return '-1'
        try:
            return str(int(float(match.group(1)) * self.SIZE_UNITS[match.group(2).upper()]))
        except (ValueError, KeyError):
            return '-1'

    def _parse_seeds(self, text):
        match = self.RE_SEEDS.search(text)
        return match.group(1) if match else '0'

    def _has_premium_audio(self, text):
        return bool(self.RE_PREMIUM_AUDIO.search(text or ''))

    def _detect_language(self, raw_title):
        # 1. Controlla se c'è l'audio ITA (rimuovendo prima i tag dei sottotitoli)
        no_sub = self.RE_SUB_ITA.sub(' ', raw_title)
        has_ita_audio = bool(self.RE_AUDIO_ITA.search(no_sub))
        has_flag = self.USE_ITA_FLAG and self.FLAG_IT in raw_title
        is_ita = has_ita_audio or has_flag

        # 2. Controlla se ci sono ESPLICITAMENTE i sottotitoli ITA
        has_sub_ita = bool(self.RE_SUB_ITA.search(raw_title))
        
        # is_sub è True SOLO se ci sono i sub ITA e NON c'è l'audio ITA
        is_sub = has_sub_ita and not is_ita

        # 3. TRUST_LANGUAGE_FILTER scatta SOLO se non ci sono indicatori di lingua
        # (cioè se il nome non dice né ITA, né SUB ITA, né ENG, ecc.)
        if not is_ita and not is_sub and self.TRUST_LANGUAGE_FILTER:
            if not self.RE_NON_ITA_LANG.search(raw_title):
                is_ita = True

        is_multi = is_ita and self._has_premium_audio(raw_title)
        
        return is_ita, is_multi, is_sub

    def _extract_codec(self, text):
        m = self.RE_CODEC.search(text)
        if not m:
            return ''
        codec = m.group(1).upper().replace(' ', '').replace('.', '').replace('_', '').replace('-', '')
        if codec in ('H265', 'HEVC', 'X265'):
            return 'H265'
        if codec in ('H264', 'X264'):
            return 'H264'
        if codec == 'AV1':
            return 'AV1'
        return ''

    def _extract_audio_info(self, text):
        if not text:
            return ''
        lower = text.lower()
        codec = ''
        if re.search(r'\bdts[\s._-]?hd[\s._-]?ma\b', lower):
            codec = 'DTS-HD MA'
        elif re.search(r'\bdts[\s._-]?hd\b', lower):
            codec = 'DTS-HD'
        elif re.search(r'\bdts[\s._-]?x\b', lower):
            codec = 'DTS-X'
        elif re.search(r'\bdts[\s._-]?es\b', lower):
            codec = 'DTS-ES'
        elif re.search(r'\bdts\b', lower):
            codec = 'DTS'
        elif re.search(r'\btruehd\b', lower):
            codec = 'TrueHD'
        elif re.search(r'\bddp\b|\bdd\+|\be[\s._-]?ac[\s._-]?3\b', lower):
            codec = 'DDP'
        elif re.search(r'\bac[\s._-]?3\b', lower):
            codec = 'AC3'
        elif re.search(r'\bdd\b', lower):
            codec = 'DD'
        elif re.search(r'\baac\b', lower):
            codec = 'AAC'
        elif re.search(r'\bflac\b', lower):
            codec = 'FLAC'
        elif re.search(r'\bopus\b', lower):
            codec = 'OPUS'
        elif re.search(r'\bmp3\b', lower):
            codec = 'MP3'
        channels = ''
        m = re.search(r'\b([1-8])[\s._-]([0-2])\b', text)
        if m:
            channels = '{}.{}'.format(m.group(1), m.group(2))
        else:
            m = re.search(r'\b([1-8])ch\b', lower)
            if m:
                ch = m.group(1)
                channels = {'1': '1.0', '2': '2.0', '6': '5.1', '8': '7.1'}.get(ch, ch + 'ch')
        has_atmos = bool(re.search(r'\batmos\b', lower))
        parts = []
        if codec:
            parts.append(codec)
        if channels:
            parts.append(channels)
        if has_atmos and codec != 'ATMOS':
            parts.append('ATMOS')
        return ' '.join(parts)

    def _extract_resolution(self, quality, first_line, raw_title=''):
        for text in (quality, first_line, raw_title):
            if not text:
                continue
            m = self.RE_RESOLUTION.search(text)
            if not m:
                continue
            token = m.group(1).lower()
            if token in ('2160p', '4k', 'uhd'):
                return '4k'
            if token in ('1440p', '2k'):
                return '1440p'
            return token
        return 'unknown'

    def _resolution_rank(self, resolution):
        try:
            return self.RESOLUTION_PRIORITY.index(resolution)
        except ValueError:
            return len(self.RESOLUTION_PRIORITY)

    def _extract_metadata(self, stream, req, filters):
        item = req['item']
        raw_title = str(stream.get('title') or '')
        lines = [line.strip() for line in raw_title.split('\n') if line.strip()]
        first_line = lines[0] if lines else 'Release'
        name_parts = [p.strip() for p in str(stream.get('name') or '').split('\n') if p.strip()]
        quality = name_parts[-1] if len(name_parts) > 1 else ''
        tracker_match = self.RE_TRACKER.search(raw_title)
        tracker = tracker_match.group(1).strip() if tracker_match else 'Torrentio'

        is_ita, is_multi, is_sub = self._detect_language(raw_title)
        if (self.ONLY_ITA or filters['ita']) and not is_ita:
            return None
        if self.ONLY_ITA_AUDIO and is_sub:
            return None

        if filters['res']:
            rx = self.RES_TOKENS[filters['res']]
            if not (rx.search(quality) or rx.search(first_line)):
                return None

        resolution = self._extract_resolution(quality, first_line, raw_title)
        if item['path_type'] in ('movie', 'series') and self.MIN_RESOLUTION:
            if resolution == 'unknown':
                if self.STRICT_RESOLUTION:
                    return None
            elif self._resolution_rank(resolution) > self._resolution_rank(self.MIN_RESOLUTION):
                return None

        is_pack = (
            item['is_series']
            and not item['id'].startswith('kitsu:')
            and not self.RE_EP_TAG.search(first_line)
        )
        if (filters['pack'] or req['season_only']) and not is_pack:
            return None

        return ParsedStream(
            first_line=first_line,
            quality=quality,
            tracker=tracker,
            is_ita=is_ita,
            is_multi=is_multi,
            is_sub=is_sub,
            is_pack=is_pack,
            codec=self._extract_codec(first_line),
            audio=self._extract_audio_info(first_line),
            resolution=resolution,
            size_bytes=self._parse_size(raw_title),
            seeds=self._parse_seeds(raw_title),
        )

    def _format_display_name(self, meta, req):
        item = req['item']
        audio_tag = ''
        if self.SHOW_AUDIO_INFO and meta.audio:
            audio_tag = '[{}] '.format(meta.audio)
        if meta.is_multi:
            lang_tag = '[MULTI] '
        elif meta.is_ita:
            lang_tag = '[ITA] '
        elif meta.is_sub:
            lang_tag = '[SUB ITA] '
        else:
            lang_tag = ''
        qual_tag = '[{}] '.format(meta.quality) if meta.quality and meta.quality.lower() != 'torrentio' else ''
        pack_tag = '[PACK] ' if meta.is_pack else ''
        codec_tag = '[{}] '.format(meta.codec) if meta.codec else ''
        year_str = ' ({})'.format(item['year']) if item['year'] else ''
        name = '{}{}{}{}{}{}{}{}'.format(
            audio_tag, lang_tag, qual_tag, pack_tag, codec_tag,
            item['title'], req['label'], year_str
        )
        if self.SHOW_RELEASE_SUFFIX and meta.first_line:
            name = '{} - {}'.format(name, meta.first_line)
        if self.SHOW_TRACKER_IN_NAME and meta.tracker:
            name = '{} [{}]'.format(name, meta.tracker)
        return name.replace('|', ' ').strip()

    def _stream_to_result(self, stream, req, filters):
        meta = self._extract_metadata(stream, req, filters)
        if not meta:
            return None
        link = self._build_magnet(stream, meta.first_line.replace('|', ' '))
        if not link:
            return None
        packet = {
            'link': link,
            'name': self._format_display_name(meta, req),
            'size': meta.size_bytes,
            'seeds': meta.seeds,
            'leech': '-1',
            'engine_url': self.url,
            'desc_link': req['item']['desc_link'],
            'pub_date': '-1'
        }
        return packet, meta

    def _hash_key(self, stream):
        return _validate_info_hash(stream.get('infoHash'))

    def _title_dedup_key(self, packet, meta):
        if not self.SMART_DEDUP:
            return None
        name = packet.get('name', '')
        name = re.sub(r'\s*\[[^\]]+\]\s*$', '', name)
        name = re.sub(r'\[[^\]]*\]', ' ', name)
        title_norm = self.RE_DEDUP_STRIP.sub('', name).lower()
        title_norm = re.sub(r'[^a-z0-9]+', '', title_norm)
        if not title_norm:
            return None
        return (
            title_norm,
            meta.resolution,
            meta.codec,
            meta.audio,
            meta.is_ita,
            meta.is_multi,
            meta.is_sub,
        )

    @staticmethod
    def _seed_sort_key(packet):
        try:
            return int(packet.get('seeds', '0'))
        except (TypeError, ValueError):
            return 0

    def _build_sort_key(self, packet, meta):
        try:
            seeds = int(packet.get('seeds', '0'))
        except (TypeError, ValueError):
            seeds = 0
        try:
            size = int(packet.get('size', '-1'))
        except (TypeError, ValueError):
            size = -1
        if size < 0:
            size = 0
        if self.SORT_STRATEGY == 'seeds':
            return (-seeds,)
        if meta.is_ita:
            lang_rank = 0
        elif meta.is_sub:
            lang_rank = 1
        else:
            lang_rank = 2
        if lang_rank == 0 and self.MIN_SEEDS_FOR_PRIORITY > 0 and seeds < self.MIN_SEEDS_FOR_PRIORITY:
            lang_rank = 3
        res_rank = self._resolution_rank(meta.resolution)
        if self.SORT_STRATEGY == 'ita_then_seeds':
            return (lang_rank, res_rank, -seeds, -size)
        return (lang_rank, res_rank, -size, -seeds)

    def search(self, what, cat='all'):
        start_time = time.monotonic()
        raw_query = urllib.parse.unquote_plus(what).strip()
        if not raw_query:
            return

        try:
            self._search_impl(raw_query, cat, start_time)
        finally:
            if self.PERSIST_STATE:
                self._auto_save_state()

    def _search_impl(self, raw_query, cat, start_time):
        season, episode, query = self._extract_season_episode(raw_query)
        if not query:
            query = raw_query

        query_before_filters = query

        query, filters = self._extract_filters(query)
        year, query_no_year = self._extract_year(query)

        if season is not None or filters['pack']:
            kinds = {'series'}
        elif cat == 'movies':
            kinds = {'movie'}
        elif cat == 'tv':
            kinds = {'series'}
        else:
            kinds = {'movie', 'series'}

        items = self._find_titles(query_no_year, query, cat, kinds, year)

        filters_active = filters['ita'] or filters['pack'] or filters['res']
        if not items and filters_active and query_before_filters != query:
            year2, qbf_no_year = self._extract_year(query_before_filters)
            self._log('retry con query originale (filtri inline): {!r}'.format(qbf_no_year))
            items = self._find_titles(qbf_no_year, query_before_filters, cat, kinds, year2 or year)

        if not items:
            self._log('nessun titolo trovato per {!r}'.format(raw_query))
            return

        all_requests = []
        for item in items:
            all_requests.extend(self._make_request(item, season, episode))

        seen_by_hash = set()
        seen_by_title = {}
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.MAX_WORKERS, len(all_requests))) as executor:
            futures = [executor.submit(self._fetch_stream, req) for req in all_requests]

            for future in concurrent.futures.as_completed(futures):
                if (time.monotonic() - start_time) > self.GLOBAL_TIMEOUT:
                    break
                try:
                    req, streams = future.result()
                except Exception:
                    continue
                for stream in streams:
                    if not isinstance(stream, dict):
                        continue
                    try:
                        result = self._stream_to_result(stream, req, filters)
                    except Exception:
                        continue
                    if not result:
                        continue
                    packet, meta = result

                    hkey = self._hash_key(stream)
                    if hkey and hkey in seen_by_hash:
                        continue
                    if hkey:
                        seen_by_hash.add(hkey)

                    tkey = self._title_dedup_key(packet, meta)
                    if tkey and tkey in seen_by_title:
                        idx = seen_by_title[tkey]
                        old_packet, old_meta = results[idx]
                        if self._seed_sort_key(packet) > self._seed_sort_key(old_packet):
                            results[idx] = (packet, meta)
                        continue
                    if tkey:
                        seen_by_title[tkey] = len(results)
                    results.append((packet, meta))

        if results:
            results.sort(key=lambda rm: self._build_sort_key(rm[0], rm[1]))

        for packet, _meta in results:
            prettyPrinter(packet)
