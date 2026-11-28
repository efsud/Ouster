import unittest
from .validate_recording_outages import truth_candidates
class OutageTruthTests(unittest.TestCase):
    def test_hidden_short_context_and_supported_are_separate(self):
        def track(key,start,end):
            return {'class_type':'2','source_key':['session',key,'2'],'points':[[t/2,t,2] for t in range(start*2,end*2+1)]}
        full={'sites':[{'id':'site','tracks':[track('supported',0,20),track('short',9,20),track('hidden',11,14),dict(track('person',0,20),class_type='10')]}]}
        ground,hidden,short=truth_candidates(full,10,15)
        self.assertEqual({k[2] for k in ground},{'supported'})
        self.assertEqual({k[2] for k in hidden},{'hidden'})
        self.assertEqual({k[2] for k in short},{'short'})
