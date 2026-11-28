"""Bounded encoded responses for the two large rolling trajectory snapshots.

The collector rewrites snapshots approximately every half hour. Parse and encode
each file signature once, not once per browser poll. Only encoded JSON and small
metadata remain cached; the parsed trajectory tree is released after loading.
Expiry is checked on every request, including conditional/version requests.
"""
from collections import OrderedDict
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
RETENTION_SECONDS = 90 * 60
ESTIMATES = {'method': 'Local within-track interpolation only', 'links': []}
WARMING_MESSAGE = 'Collecting the first samples. Initial figure appears after about 30 seconds.'
EXPIRED_MESSAGE = 'Snapshot expired; rolling collector must be running.'


def _encode(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':')).encode('utf-8')


def _signature(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


class SnapshotCache:
    """At most two encoded payloads; one load lock bounds concurrent parsing.

    Region aliases are canonicalized before caching. Callers cannot supply an
    arbitrary file path. Use a separate instance with folders for isolated tests.
    """
    def __init__(self, folders=None, retention_seconds=RETENTION_SECONDS):
        self.folders = folders or {
            'Florida': ROOT/'data/florida-rolling',
            'Toronto': ROOT/'data/finch-rolling',
        }
        self.retention_seconds = float(retention_seconds)
        self._entries = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _region(region):
        aliases = {'Florida': 'Florida', 'florida': 'Florida',
                   'Toronto': 'Toronto', 'toronto': 'Toronto',
                   'Finch': 'Toronto', 'finch': 'Toronto'}
        if region not in aliases:
            raise ValueError('Unknown rolling corridor')
        return aliases[region]

    def _warming(self):
        return _encode({'state': 'warming', 'message': WARMING_MESSAGE})

    def _load(self, region, path, now):
        # An atomic collector replacement leaves this opened file consistent.
        # An in-place writer is detected by the second fstat and never cached.
        with path.open('rb') as source:
            signature = _signature(os.fstat(source.fileno()))
            data = json.load(source)
            if signature != _signature(os.fstat(source.fileno())):
                raise ValueError('Snapshot changed while loading')
        if not isinstance(data, dict):
            raise ValueError('Snapshot is not an object')
        start = data.get('start')
        if isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start):
            raise ValueError('Snapshot start is unavailable')
        expires_at = float(start) + self.retention_seconds
        version = hashlib.sha256((region+':'+':'.join(str(v) for v in signature)).encode()).hexdigest()[:24]
        metadata = {k: data.get(k) for k in ('generated_at', 'start', 'end', 'next_update')}
        if any(value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value))
               for value in metadata.values()):
            raise ValueError('Snapshot time metadata is invalid')
        metadata.update(version=version, expires_at=expires_at)
        entry = dict(signature=signature, metadata=metadata, body=None)
        if now <= expires_at:
            # Match existing read_snapshot: old experiment paths are suppressed.
            data.update(state='ready', estimates=ESTIMATES, version=version, expires_at=expires_at)
            entry['body'] = _encode(data)
        # Do not retain data, tracks, JSON decoder objects or source text.
        return entry

    def read(self, region, since=None, now=None):
        """Return already encoded application/json bytes.

        `since` must be the exact opaque `version` from a full ready response.
        A numeric generated_at is deliberately not accepted as a version: a
        rewritten file can retain that timestamp while its contents change.
        """
        region = self._region(region)
        now = time.time() if now is None else float(now)
        path = Path(self.folders[region])/'snapshot.json'
        with self._lock:
            try:
                signature = _signature(path.stat())
                entry = self._entries.get(region)
                if entry is None or entry['signature'] != signature:
                    # Drop the old encoded generation before allocating its
                    # replacement; active HTTP writers may finish their copy.
                    self._entries.pop(region, None)
                    entry = None
                    entry = self._load(region, path, now)
                    self._entries[region] = entry
                self._entries.move_to_end(region)
                while len(self._entries) > 2:
                    self._entries.popitem(last=False)
            except (OSError, ValueError, TypeError, OverflowError):
                # Missing/malformed replacement must not serve an older payload.
                self._entries.pop(region, None)
                return self._warming()
            meta = entry['metadata']
            if now > meta['expires_at']:
                entry['body'] = None  # Release the potentially large expired hour.
                return _encode(dict(meta, state='expired', message=EXPIRED_MESSAGE))
            if entry['body'] is None:
                # A backwards test/system clock must not revive a discarded body.
                return _encode(dict(meta, state='expired', message=EXPIRED_MESSAGE))
            if since is not None and str(since) == meta['version']:
                return _encode(dict(meta, state='unchanged'))
            return entry['body']


CACHE = SnapshotCache()


def get_response(region, since=None, now=None):
    """Handler: send(get_response(...), mime='application/json; charset=utf-8')."""
    return CACHE.read(region, since=since, now=now)
