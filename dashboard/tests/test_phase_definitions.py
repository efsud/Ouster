import unittest
from dashboard.phase_definitions import check_definition
from dashboard.signals import apply_change

class DefinitionCheckTest(unittest.TestCase):
    def test_configuration_is_not_current_color_or_verified_join(self):
        definitions={'rows':[{'active':True,'phase_id':900,'phase_label':'4','allowed_movements':[{'turningMovement':'SN','trafficLightStatus':'green'},{'turningMovement':'SE','trafficLightStatus':'red'}]}]}
        c=check_definition('S',['4'],'NS',definitions)
        self.assertTrue(c['conflict']);self.assertFalse(c['join_verified'])
        self.assertFalse(check_definition('S',['4'],'SN',definitions)['conflict'])
        self.assertEqual(check_definition('S',['900'],'NS',definitions)['matches'],[])
        self.assertTrue(check_definition('S',['4'],'SE',definitions)['conflict'])
    def test_delta_uses_phase_change_timestamp(self):
        state={}
        apply_change(state,'s',{'absolute':True,'phases':[{'phaseNumber':'2','status':1,'timestamp':'2026-11-16T10:00:01'}]},1)
        apply_change(state,'s',{'timestamp':'2026-11-16T10:00:02','phases':[{'phaseNumber':'2','status':3}]},2,'2026-11-16T10:00:00')
        self.assertEqual(state['phases']['2']['status'],'RED')
        self.assertEqual(state['phases']['2']['sensor_timestamp'],'2026-11-16T10:00:02')
