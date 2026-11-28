import unittest
from unittest.mock import patch
from .archive_extension import cases
from .validate_vehicle_classes import calibration


class VehicleClassTests(unittest.TestCase):
    def test_default_masks_still_only_cars(self):
        tracks = [dict(class_type=c, source_key=['session', c], direction='eastbound',
                       points=[[0, 0, 1], [120, 120, 1]]) for c in ('2', '4', '5')]
        snapshot = {'sites': [{'id': 'site', 'tracks': tracks}]}
        with patch('deepctm.archive_extension.masked_case', return_value=(1, 2, 3)):
            self.assertEqual({r[2]['class_type'] for r in cases(snapshot, 'test')}, {'2'})
            self.assertEqual({r[2]['class_type'] for r in cases(snapshot, 'test', classes=('4', '5'))}, {'4', '5'})

    def test_calibration_requires_distinct_ids_not_fragment_count(self):
        track = dict(class_type='4', source_key=['session', 'same-id'],
                     points=[[i / 2, i, 10] for i in range(120)])
        params, evidence = calibration({'sites': [{'id': 'site', 'tracks': [track] * 12}]}, '4')
        self.assertIsNone(params)
        self.assertEqual(evidence['distinct_training_ids'], 1)
