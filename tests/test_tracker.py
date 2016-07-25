import unittest
from pythorrent.peer_stores import Tracker
from datetime import datetime, timedelta

class TestTrackerAnnounce(unittest.TestCase):
    def setUp(self):
        self.tracker = Tracker("", None)
        self.now = datetime.utcnow()
        
    def test_announce_ok_when_not_set(self):
        self.tracker.last_run = None
        self.assertTrue(self.tracker.ok_to_announce)
        
    def test_announce_ok_when_last_run_in_past(self):
        self.tracker.last_run = self.now - self.tracker.delta
        self.assertTrue(self.tracker.ok_to_announce)
        
    def test_announce_ok_when_last_run_in_future(self):
        self.tracker.last_run = self.now + self.tracker.delta
        self.assertFalse(self.tracker.ok_to_announce)
        
        
