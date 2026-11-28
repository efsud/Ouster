import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dashboard.rolling_response import SnapshotCache


class RollingResponseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.folders = {region: root/region for region in ('Florida', 'Toronto')}
        for folder in self.folders.values():
            folder.mkdir()
        self.cache = SnapshotCache(self.folders)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, region='Florida', **updates):
        value = dict(start=1000., end=4600., generated_at=4600.,
                     sites=[{'id': region, 'tracks': [{'points': [[0, 10, 2], [1, 12, 2]]}]}],
                     estimates={'links': [{'old': 'experimental paths'}]})
        value.update(updates)
        folder = self.folders[region]
        temporary = folder/'snapshot.tmp'
        temporary.write_text(json.dumps(value)); temporary.replace(folder/'snapshot.json')
        return value

    def test_ready_preserves_observations_and_sanitizes_estimates(self):
        original = self.save()
        value = json.loads(self.cache.read('Florida', now=5000))
        self.assertEqual(value['state'], 'ready')
        self.assertEqual(value['sites'], original['sites'])
        self.assertEqual(value['estimates']['links'], [])
        self.assertEqual(value['expires_at'], 6400.)
        self.assertTrue(value['version'])

    def test_repeated_and_conditional_requests_parse_only_once(self):
        self.save()
        with patch('dashboard.rolling_response.json.load', wraps=json.load) as loader:
            full = self.cache.read('Florida', now=5000)
            version = json.loads(full)['version']
            again = self.cache.read('florida', now=5001)
            small = self.cache.read('Florida', since=version, now=5002)
            self.assertIs(full, again)
            self.assertEqual(loader.call_count, 1)
        value = json.loads(small)
        self.assertEqual(value['state'], 'unchanged')
        self.assertEqual(value['generated_at'], 4600)
        self.assertNotIn('sites', value)
        self.assertLess(len(small), 300)

    def test_expiry_overrides_matching_version_and_releases_payload(self):
        self.save()
        full = json.loads(self.cache.read('Florida', now=6400))
        self.assertEqual(full['state'], 'ready')
        expired = json.loads(self.cache.read('Florida', since=full['version'], now=6400.01))
        self.assertEqual(expired['state'], 'expired')
        self.assertIsNone(self.cache._entries['Florida']['body'])
        self.assertNotIn('sites', expired)

    def test_same_timestamp_replacement_invalidates_old_version(self):
        self.save(); old = json.loads(self.cache.read('Florida', now=5000))
        self.save(sites=[{'id': 'new'}])
        new = json.loads(self.cache.read('Florida', since=old['version'], now=5001))
        self.assertEqual(new['state'], 'ready')
        self.assertNotEqual(new['version'], old['version'])
        self.assertEqual(new['sites'], [{'id': 'new'}])
        # An old generated_at cannot hide changed content either.
        self.assertEqual(json.loads(self.cache.read('Florida', since='4600.0', now=5002))['state'], 'ready')

    def test_region_isolation_and_only_two_encoded_entries(self):
        self.save(); self.save('Toronto')
        florida = json.loads(self.cache.read('Florida', now=5000))
        finch = json.loads(self.cache.read('Finch', now=5000))
        self.assertNotEqual(florida['version'], finch['version'])
        self.assertEqual(finch['sites'][0]['id'], 'Toronto')
        self.assertEqual(len(self.cache._entries), 2)
        self.assertEqual(set(self.cache._entries['Florida']), {'signature', 'metadata', 'body'})
        self.assertIsInstance(self.cache._entries['Florida']['body'], bytes)
        with self.assertRaises(ValueError):
            self.cache.read('../../private', now=5000)

    def test_missing_or_bad_file_does_not_serve_old_cache(self):
        self.assertEqual(json.loads(self.cache.read('Florida', now=5000))['state'], 'warming')
        self.save(); self.cache.read('Florida', now=5000)
        path = self.folders['Florida']/'snapshot.json'
        path.write_text('{broken')
        self.assertEqual(json.loads(self.cache.read('Florida', now=5000))['state'], 'warming')
        self.assertNotIn('Florida', self.cache._entries)
        self.save(start='invalid')
        self.assertEqual(json.loads(self.cache.read('Florida', now=5000))['state'], 'warming')

    def test_concurrent_browser_requests_share_one_load(self):
        self.save()
        with patch('dashboard.rolling_response.json.load', wraps=json.load) as loader:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                bodies = list(pool.map(lambda _: self.cache.read('Florida', now=5000), range(16)))
            self.assertEqual(loader.call_count, 1)
        self.assertTrue(all(body is bodies[0] for body in bodies))


if __name__ == '__main__':
    unittest.main()
