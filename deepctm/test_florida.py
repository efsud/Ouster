from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from .florida_preview import locate, dashboard_status
from .florida_tracks import calibration, events, extract


SITE = {'id':'OBC-AG-SA-C257222', 'station_m':200}
START = 1794520800


def record(t, x=0, ident='a', session='one', clock=None, cls='2'):
    stamp=datetime.fromtimestamp(START + (t if clock is None else clock), timezone.utc).isoformat()
    objects=[] if ident is None else [{'id':ident,'centerX':x,'centerY':0,'classType':cls}]
    return {'site':SITE['id'], 'session':session, 'received_at':START+t,
            'payload':{'frame':{'timestamp':stamp,'objects':objects}}}


class FloridaTests(unittest.TestCase):
    def extract(self, rows, cal=None):
        return extract(rows,SITE,START,START+3600,Counter(),cal)

    def test_calibration_is_required_for_distance_and_direction(self):
        r=[record(0,0),record(.5,5),record(1,10)]
        tracks,stats=self.extract(r)
        self.assertEqual(stats['frames'],3)
        self.assertEqual(tracks,[['2','unknown',[[0,200,.5,200,36],[.5,200,1,200,36]]]])
        cal=calibration(dict(east_unit_xy=[-1,0],origin_station_offset_m=20,
                             origin_lat=28.66,origin_lon=-81.38,roi_m=[-50,50,-10,10],source='fixture'))
        tracks,_=self.extract(r,cal)
        self.assertEqual(tracks[0][1],'westbound')
        self.assertEqual(tracks[0][2][0],[0,220,.5,215,36])

    def test_never_bridges_absence_id_class_or_session(self):
        tracks,stats=self.extract([record(0),record(.1,1),record(.2,ident=None),
            record(.3,3),record(.4,4,ident='b'),record(.5,5,ident='b',cls='3'),
            record(.6,6,ident='b',cls='3',session='two'),record(.7,7,ident='b',cls='3',session='two')])
        self.assertEqual([t[2][0][0] for t in tracks],[0,.6])
        self.assertEqual(stats['sessions'],2)
        self.assertGreaterEqual(stats['diagnostics']['object_disappearances'],3)

    def test_clock_discontinuity_and_gaps(self):
        tracks,stats=self.extract([record(0),record(.5,5),record(1,10,clock=.1),
                                   record(9,90),record(9.5,95),record(10,100)])
        self.assertEqual(stats['gaps_over_3s'],2)
        self.assertEqual(stats['receipt_span_s'],10)
        self.assertGreaterEqual(stats['diagnostics']['sensor_clock_step_breaks'],1)
        for _,_,pairs in tracks:
            self.assertTrue(all(b-a<=1 for a,_,b,_,_ in pairs))

    def test_display_sampling_does_not_connect_nonadjacent_pairs(self):
        tracks,_=self.extract([record(i/10,i) for i in range(11)])
        pairs=tracks[0][2]
        self.assertEqual(len(pairs),3)
        self.assertTrue(all(abs(b-a-.1)<.001 for a,_,b,_,_ in pairs))

    def test_archive_invalid_row_and_sensor_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            with gzip.open(d/(SITE['id']+'-one.jsonl.gz'),'wt') as f:
                f.write('invalid JSON\n'+json.dumps(record(.5))+'\n')
            issues=Counter()
            self.assertEqual(list(events(d,SITE['id'],issues)),[record(.5)])
            self.assertEqual(issues['invalid_archive_rows'],1)

    def test_empty_capture_is_not_reception(self):
        tracks,stats=self.extract([])
        self.assertFalse(tracks)
        self.assertEqual(stats['frames'],0)
        self.assertIsNone(stats['first_receipt'])
        self.assertEqual(stats['longest_gap_s'],3600)

    def test_dashboard_rejects_traversal_and_handles_no_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            self.assertEqual(dashboard_status(d)['state'],'not_started')
            (d/'latest.json').write_text('{"capture_id":"../toronto"}')
            with self.assertRaises(ValueError):
                locate(d)


if __name__=='__main__':
    unittest.main()
