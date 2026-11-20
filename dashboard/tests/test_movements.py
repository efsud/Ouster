import unittest
from dashboard.movements import classify,route,MOVEMENTS,VECTORS

class MovementTests(unittest.TestCase):
    def path(self,a,b):
        av=VECTORS[a];bv=VECTORS[b]
        xy=[(av[0]*d,av[1]*d) for d in range(60,0,-5)]+[(0,0)]+[(bv[0]*d,bv[1]*d) for d in range(5,65,5)]
        return [(i*.5,x,y) for i,(x,y) in enumerate(xy)]
    def test_all_twelve(self):
        for code in MOVEMENTS:
            result=classify(self.path(*code));self.assertEqual(result.get('movement'),code)
        self.assertEqual(MOVEMENTS['NE']['turn'],'left');self.assertEqual(MOVEMENTS['NW']['turn'],'right')
        self.assertEqual(MOVEMENTS['WN']['turn'],'left');self.assertEqual(MOVEMENTS['WS']['turn'],'right')
    def test_exit_ends_corridor_but_can_arrive_from_previous(self):
        r=route('WN');self.assertTrue(r['can_match_previous']);self.assertFalse(r['can_match_next']);self.assertEqual(r['incoming_direction'],'eastbound')
    def test_entry_starts_corridor(self):
        r=route('NE');self.assertFalse(r['can_match_previous']);self.assertTrue(r['can_match_next']);self.assertEqual(r['outgoing_direction'],'eastbound')
    def test_partial_and_side_road(self):
        self.assertEqual(classify(self.path('W','E')[:8])['state'],'unknown')
        r=classify(self.path('N','S'));self.assertFalse(r['can_match_next']);self.assertFalse(r['can_match_previous'])
    def test_gap_and_uturn_not_invented(self):
        p=self.path('W','E');self.assertEqual(classify(p[:8]+p[20:])['state'],'unknown')
        self.assertEqual(classify(self.path('W','W'))['state'],'unknown')

class PhaseEvidenceTests(unittest.TestCase):
    def test_no_signal_history_never_assigns_phase(self):
        from dashboard.movement_phases import summarize
        p=MovementTests().path('W','E');r=summarize([{'key':('session','1','1'),'points':p,'movement':classify(p)}],[])
        self.assertEqual(len(r['movements']),12);self.assertTrue(all(not m['phase_numbers'] for m in r['movements']))
        self.assertEqual(next(m for m in r['movements'] if m['movement']=='WE')['observed_tracks'],1)
    def test_initial_wait_does_not_change_geometry(self):
        p=MovementTests().path('W','E');wait=[(i*.5,p[0][1],p[0][2]) for i in range(10)]
        p=wait+[(t+5,x,y) for t,x,y in p]
        self.assertEqual(classify(p)['movement'],'WE')
    def phase_fixture(self,duplicate=False):
        import json
        rows=[];tracks=[]
        for t in range(0,901,5):
            status='GREEN' if t%60<20 else 'RED'
            phases={'2':{'status':status,'received_at':t}}
            if duplicate:phases['6']=dict(phases['2'])
            rows.append((t,'s',json.dumps({'initialized':True,'phases':phases})))
        for cycle in range(1,15):
            t=cycle*60+5;points=[(t-4,-40,0),(t-3,-40,0),(t-2,-40,0),(t-1,-40,0),(t,-35,0),(t+1,-25,0),(t+2,-15,0),(t+3,-5,0),(t+4,5,0)]
            tracks.append({'key':('s',str(cycle),'1'),'points':points,'movement':{'movement':'WE','role':'through'}})
        return tracks,rows
    def test_repeated_phase_evidence_and_correlated_ambiguity(self):
        from dashboard.movement_phases import summarize
        result=summarize(*self.phase_fixture());we=next(m for m in result['movements'] if m['movement']=='WE')
        self.assertEqual(we['phase_numbers'],['2']);self.assertEqual(we['phase_mapping'],'estimated')
        result=summarize(*self.phase_fixture(True));we=next(m for m in result['movements'] if m['movement']=='WE')
        self.assertEqual(we['phase_numbers'],[])
    def test_wrong_session_cannot_decode(self):
        from dashboard.movement_phases import summarize
        tracks,rows=self.phase_fixture()
        for t in tracks:t['key']=('different',t['key'][1],'1')
        self.assertTrue(all(not m['phase_numbers'] for m in summarize(tracks,rows)['movements']))
    def test_distant_queue_creep_is_not_phase_evidence(self):
        from dashboard.movement_phases import summarize
        tracks,rows=self.phase_fixture()
        for track in tracks:
            t=track['points'][4][0]
            track['points']=[(t-4,-120,0),(t-3,-120,0),(t-2,-120,0),(t-1,-120,0),(t,-115,0)]+[(t+i,-115+10*i,0) for i in range(1,15)]
        we=next(m for m in summarize(tracks,rows)['movements'] if m['movement']=='WE')
        self.assertEqual(we['qualifying_releases'],0);self.assertEqual(we['phase_numbers'],[])
