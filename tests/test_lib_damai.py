from lib.damai import Damai
import unittest

class Test(unittest.TestCase):
    def setUp(self):
        self.inst = Damai()

    def tearDown(self):
        pass

    def test_get_concert_from_web(self):
        result = self.inst.get_concert_from_web()

    def test_get_concert_from_db(self):
        result = self.inst.get_concert_from_db()

    def test_get_performs_from_web(self):
        result = self.inst.get_performs_from_web(149252)
        print(result)

    def test_get_price_list_from_web(self):
        result = self.inst.get_price_list_from_web(149252, 9049689)
        print(result)

    def test_get_concerts_price_list_from_web(self):
        self.inst.get_concerts_price_list_from_web()

    def test_get_concert_tickets_from_db(self):
        self.inst.get_concert_tickets_from_db(9049689)
