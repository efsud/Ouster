import unittest
from unittest.mock import patch,MagicMock
from scripts import start_connected

class LauncherTest(unittest.TestCase):
    def test_duration_stops_entire_collector_groups(self):
        child=MagicMock();child.pid=12345;child.poll.return_value=None
        with patch('sys.argv',['launcher','--toronto','--duration','2']), \
             patch.object(start_connected.socket,'socket'), \
             patch.object(start_connected.sys.stdin,'isatty',return_value=True), \
             patch.object(start_connected.importlib.util,'find_spec',return_value=True), \
             patch('dashboard.storage.Store'), \
             patch('builtins.input',return_value='test-account'), \
             patch.object(start_connected.getpass,'getpass',return_value='test-only'), \
             patch.object(start_connected.subprocess,'Popen',return_value=child) as popen, \
             patch.object(start_connected.time,'monotonic',side_effect=[0,1,2]), \
             patch.object(start_connected.time,'sleep'), \
             patch.object(start_connected.os,'killpg') as kill, \
             patch('builtins.print'):
            start_connected.main()
        self.assertEqual(popen.call_count,11)
        self.assertTrue(all(c.kwargs['start_new_session'] for c in popen.call_args_list))
        self.assertEqual(kill.call_count,11)
        self.assertTrue(all(c.args[1]==start_connected.signal.SIGINT for c in kill.call_args_list))
        self.assertEqual(child.wait.call_count,11)
