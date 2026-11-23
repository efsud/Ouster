import unittest
from .transform_manifest import manifest
class TransformManifestTests(unittest.TestCase):
    def test_order_stable_but_reflection_and_origin_change_version(self):
        a={'id':'A','reference_location':{'lat':1,'lng':2}}
        b={'id':'B','reference_location':{'lat':3,'lng':4}}
        before=manifest([a,b])['sha256']
        self.assertEqual(before,manifest([b,a])['sha256'])
        self.assertNotEqual(before,manifest([dict(a,preview_mirror_y=True),b])['sha256'])
        self.assertNotEqual(before,manifest([dict(a,reference_location={'lat':1.1,'lng':2}),b])['sha256'])
