import datetime
import re
import json
import requests
import pymongo
from lxml import etree
import lib.utils

class Motianlun(object):
    def __init__(self):
        client = pymongo.MongoClient()
        self.db = client.ticket

    def get_session_oid(self, from_dt, keyword=""):
        url_patt = "https://www.moretickets.com/search/{}?city=3101&offset={}&length=10&&startTime={}&endTime={}"
        i = 0
        date_str = from_dt.strftime("%Y%m%d")
        url = url_patt.format(keyword, i, date_str, date_str)
        r = requests.get(url, verify=False)
        i += 10
        content = r.content.decode("utf-8")
        root = etree.HTML(content)
        div_node = root.find('.//div[@class="shows-container"]')
        a_nodes = div_node.xpath('./a[contains(@class, "show-items")]')
        if len(a_nodes) == 0:
            print("no shows for {} at {}".format(keyword, from_dt))
            return None
        if len(a_nodes) > 1:
            print("need investigate - {} has multiple shows at {}".format(keyword, from_dt))
            return None
        show_oid = a_nodes[0].attrib.get("data-sashowoid")
        session_oid = self.get_session_oid_by_time(show_oid, from_dt)
        return session_oid

    def get_session_oid_by_time(self, show_oid, from_dt):
        url_patt = "https://www.moretickets.com/showapi/pub/v1_1/show/{}/sessionone?src=web&sessionOID=".format(show_oid)
        r = requests.get(url_patt, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        timestamp = from_dt.timestamp() * 1000
        items = data["result"]["data"]
        items = list(filter(lambda x: x.get("showTime_long") == timestamp, items))
        if len(items) == 0:
            print("cannot find session for show {} at {}".format(show_oid, from_dt))
            return None
        if len(items) > 1:
            print("multiple shows for show {} at {}".format(show_oid, from_dt))
            return None
        return items[0]["showSessionOID"]

    def get_session_mapping(self):
        concerts = self.db.concert.aggregate([
            {"$unwind": "$performs"},
        ])
        for concert in concerts:
            name = concert["name"]
            timestamp = concert["performs"]["start_time"]
            performid = concert["performs"]["performid"]
            existing = self.db.motianlun_mapping.find({"performid": performid}).count()
            if existing > 0:
                continue
            show_dt = datetime.datetime.fromtimestamp(timestamp)
            actor_str = concert["actors"]
            venue_str = concert["venue"]
            actor = actor_str.split(":")[-1].strip()
            print(name)
            session_oid = None
            if actor:
                keyword = actor
                session_oid = self.get_session_oid(show_dt, keyword)
                if session_oid is not None:
                    mapping = {"performid": performid,
                        "session_oid": session_oid}
                    self.db.motianlun_mapping.insert_one(mapping)
                    continue

            keywords = lib.utils.get_keyword(name)
            for keyword in keywords:
                session_oid = self.get_session_oid(show_dt, keyword)
                if session_oid:
                    mapping = {"performid": performid,
                        "session_oid": session_oid}
                    self.db.motianlun_mapping.insert_one(mapping)
                    break

    def get_presale_status(self, show_oid, session_oid):
        url_patt = "https://www.moretickets.com/showapi/pub/v1_1/show/{}/sessionone?time=&src=web&sessionOID="
        url = url_patt.format(show_oid)
        r = requests.get(url, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        if data["statusCode"] == 1001:
            print("error with {}".format(url))
            return
        sessions = data["result"]["data"]
        if len(sessions) == 0:
            return
        session = sessions[0]
        presale = session["showStatus"]["code"] == 2
        return presale

    def get_session_show_oid(self, session_oid):
        url_patt = "https://appapi.moretickets.com/showapi/pub/showSession/{}/seatplans/sale?isSupportSession=1&src=ios&ver=4.8.1"
        url = url_patt.format(session_oid)
        r = requests.get(url, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        if data["statusCode"] != 200:
            print("error with {}".format(url))
            return None
        show_oid = data["result"]["data"][0]["showOID"]
        return show_oid

    def get_session_tickets(self, session_oid):
        url_patt = "https://appapi.moretickets.com/showapi/pub/showSession/{}/seatplans/sale?isSupportSession=1&src=ios&ver=4.8.1"
        url = url_patt.format(session_oid)
        r = requests.get(url, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        if data["statusCode"] == 1001:
            print("error with {}".format(url))
            return []
        print(url)
        items = data["result"]["data"]
        show_oid = self.get_session_show_oid(session_oid)
        pre_sale = self.get_presale_status(show_oid, session_oid)
        result = []
        for item in items:
            face_price = float(item["originalPrice"])
            section = item["comments"]
            for ticket in item["tickets"]:
                result.append({
                    "ticket_oid": ticket["ticketOID"],
                    "seller": ticket["sellerName"],
                    "face_price": face_price,
                    "deal_price": float(ticket["price"]),
                    "section": section,
                    "pre_sale": pre_sale,
                })
        return result

    def find_std_price(self, performid, price, section):
        items = self.db.std_price.find({"performid": performid, "price": price})
        items = list(map(lambda x: x, items))
        if len(items) == 0:
            return None
        if len(items) == 1:
            return items[0]
        if len(items) > 1:
            matched_section = list(filter(lambda x: re.search(section, x["name"]), items))
            if len(matched_section) == 1:
                return matched_section[0]
            else:
                msg = "need investigate - cannot find exactly one matching for {} {} {}".format(performid, price, section)
                print(msg)
                return items[0]

    def get_session_asks(self):
        sessions = self.db.concert.aggregate([
            {"$unwind": "$performs"},
            {"$lookup": {"from": "motianlun_mapping", "localField": "performs.performid", "foreignField": "performid", "as": "motianlun_mapping"}},
            {"$match": {"motianlun_mapping": {"$ne": []}}},
            {"$unwind": "$motianlun_mapping"},
        ])
        for session in sessions:
            session_oid = session["motianlun_mapping"]["session_oid"]
            performid = session["performs"]["performid"]
            tickets = self.get_session_tickets(session_oid)
            now = datetime.datetime.now()
            for ticket in tickets:
                matched = self.find_std_price(performid, ticket["face_price"], ticket["section"])
                if matched is None:
                    continue
                existing = self.db.motianlun_ask.find({"ticket_oid": ticket["ticket_oid"]}).count()
                if existing > 0:
                    continue
                item = {
                    "ticket_oid": ticket["ticket_oid"],
                    "priceid": matched["priceid"],
                    "ask": ticket["deal_price"],
                    "seller": ticket["seller"],
                    "section": ticket["section"],
                    "when_created": now,
                }
                self.db.motianlun_ask.insert_one(item)
                print("insert one price")

    def get_asks_by_priceid(self, priceid):
        items = self.db.motianlun_ask.find({"priceid": priceid})
        result = []
        for item in items:
            result.append({
                "priceid": item["priceid"],
                "ask": item["ask"],
                "seller": item["seller"],
                "section": item["section"],
            })
        return result

    @staticmethod
    def get_commission(price):
        comm = 0
        if price <= 200:
            comm = 10
        elif price <= 400:
            comm = 20
        elif price <= 800:
            comm= 30
        else:
            comm = 50
        return comm

