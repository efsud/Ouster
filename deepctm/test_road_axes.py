import unittest
from .road_axes import nearest_axis,road_contains
class RoadAxesTests(unittest.TestCase):
    def ways(self,name='Finch Avenue West'):
        return [{'tags':{'name':name},'geometry':[{'lat':0,'lon':-.001},{'lat':0,'lon':0},{'lat':0,'lon':.001}]}]
    def test_uses_road_not_corridor_chord(self):
        self.assertAlmostEqual(nearest_axis({'lat':0,'lng':0},self.ways(),'Finch Avenue West')['bearing_deg'],0)
    def test_wrong_road_or_remote_segment_cannot_supply_axis(self):
        self.assertIsNone(nearest_axis({'lat':0,'lng':0},self.ways(),'Other Road'))
        self.assertIsNone(nearest_axis({'lat':1,'lng':0},self.ways(),'Finch Avenue West'))

    def test_offset_carriageway_kept_side_road_rejected(self):
        segments=[[[-100,25],[100,25]]]
        self.assertTrue(road_contains(50,25,segments))
        self.assertFalse(road_contains(0,60,segments))
        self.assertFalse(road_contains(200,25,segments))
