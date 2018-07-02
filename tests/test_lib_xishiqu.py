import datetime
from lib.xishiqu import Xishiqu
import unittest

class Test(unittest.TestCase):
    def setUp(self):
        self.inst = Xishiqu()

    def tearDown(self):
        pass

    def test_get_event_id(self):
        dt1 = datetime.datetime.strptime("2018-08-04 19:30", "%Y-%m-%d %H:%M")
        dt2 = datetime.datetime.strptime("2018-08-05 19:30", "%Y-%m-%d %H:%M")
        actor = "邓紫棋"
        result = self.inst.get_event_id(dt1, actor)
        print(result)
        result = self.inst.get_event_id(dt2, actor)
        print(result)

    def test_get_event_mapping(self):
        self.inst.get_event_mapping()

    def test_get_perform_tickets(self):
        url = "http://www.xishiqu.com/event/pjhychshz/all/p1.html?specialId=304"
        result = self.inst.get_perform_tickets(url)
        print(result)

    def test_get_event_tickets(self):
        event_id = 262862
        result = self.inst.get_event_tickets(event_id)
        print(result)

    def test_get_events_asks(self):
        result = self.inst.get_events_asks()
        print(result)

    def test_find_std_price(self):
        result = self.inst.find_std_price(9049690, 1280, section)
        print(result)

    def test_get_events_asks(self):
        result = self.inst.get_events_asks()
        print(result)

    def test_get_commission(self):
        result = Xishiqu.get_commission(100)
        print(result)
        result = Xishiqu.get_commission(200)
        print(result)
        result = Xishiqu.get_commission(400)
        print(result)
        result = Xishiqu.get_commission(800)
        print(result)
        result = Xishiqu.get_commission(1000)
        print(result)
