import datetime
from lib.motianlun import Motianlun
import unittest

class Test(unittest.TestCase):
    def setUp(self):
        self.inst = Motianlun()

    def tearDown(self):
        pass

    def test_get_session_oid(self):
        from_dt = datetime.datetime.strptime("2018-08-04", "%Y-%m-%d")
        keyword = "邓紫棋"
        self.inst.get_session_oid(from_dt, keyword)

    def test_get_session_mapping(self):
        self.inst.get_session_mapping()

    def test_get_session_oid_by_time(self):
        from_dt = datetime.datetime.fromtimestamp(1540120500)
        result = self.inst.get_session_oid_by_time("59eeee74a251d86dd7c80cf0", from_dt)
        print(result)

    def test_get_session_tickets(self):
        result = self.inst.get_session_tickets("5b15088e908c3865cd8c0260")
        print(result)

    def test_get_session_asks(self):
        self.inst.get_session_asks()

    def test_get_session_show_oid(self):
        session_oid = "5b15088e908c3865cd8c0260"
        result = self.inst.get_session_show_oid(session_oid)
        print(result)

    def test_get_session_asks(self):
        self.inst.get_session_asks()
