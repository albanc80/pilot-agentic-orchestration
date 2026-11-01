import unittest

class Drills(unittest.TestCase):
    def test_deliberate_failure(self):
        self.assertEqual(1, 2, "intentional red check for D07 drill")
