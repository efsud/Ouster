import json
import unittest
from datetime import datetime, timedelta
from .moderate_delivery_timing import correct, correct_for_build
from .delivery_timing import correct as baseline


class ModerateDeliveryTests(unittest.TestCase):
    def rows(self, delay=.8):
        return [('s', 1000+i*.1+(max(0, delay-(i-80)*.02) if i >= 80 else 0),
                 json.dumps({'timestamp': (datetime(2026, 1, 1)+timedelta(seconds=i*.1)).isoformat(), 'frame': {'objects': [{'id': i}]}}))
                for i in range(300)]

    def test_small_bounded_burst_recovers_known_times(self):
        rows = self.rows()
        old, _ = baseline(rows)
        self.assertEqual([r[1] for r in old], [r[1] for r in rows])
        result, audit = correct(rows)
        self.assertGreater(audit['candidate'][0]['additional_corrected_frames'], 0)
        self.assertLess(max(abs(row[1]-(1000+i*.1)) for i, row in enumerate(result)), .01)
        self.assertEqual([(r[0], r[3], r[2]) for r in result], rows)

    def test_real_missing_frames_are_not_filled(self):
        rows = self.rows(0)
        rows = rows[:80]+rows[100:]
        result, audit = correct(rows)
        self.assertEqual([r[1] for r in result], [r[1] for r in rows])
        self.assertEqual(len(result), len(rows))

    def test_duplicate_or_unbounded_clock_not_repaired(self):
        for mode in ('duplicate', 'no_return'):
            rows = self.rows()
            if mode == 'no_return':
                rows = rows[:100]
            else:
                rows[100] = (rows[100][0], rows[100][1], rows[99][2])
            result, audit = correct(rows)
            self.assertEqual([r[1] for r in result], [r[1] for r in rows])

    def test_production_corrections_preserved(self):
        rows = self.rows(5)
        old, _ = baseline(rows)
        result, audit = correct(rows)
        self.assertEqual(result, old)

    def test_adapter_labels_events_and_preserves_audit_shape(self):
        rows = self.rows()
        expected, details = correct(rows)
        output, audit = correct_for_build(rows)
        self.assertEqual(output, expected)
        self.assertIsInstance(audit, list)
        self.assertEqual(audit[0]['moderate_corrected_frames'], details['candidate'][0]['additional_corrected_frames'])
        self.assertTrue(all(e['method'] == 'moderate_bounded_delivery_v1' for e in audit[0]['events']))
        self.assertEqual(audit[0]['corrected_frames'], audit[0]['moderate_corrected_frames'])
