import datetime
import re
import json
import requests
import pymongo
from lxml import etree
import lib.utils

def fix_space(string):
    string = string.replace(u'\xa0', u' ')
    return string

class Xishiqu(object):
    def __init__(self):
        client = pymongo.MongoClient()
        self.db = client.ticket

    def get_event_id(self, from_dt, keyword=""):
        url = "http://www.xishiqu.com/cate/yanchanghui/"
        format1 = "%Y-%m-%d"
        format2 = "%Y%m%d"
        days = "f{}e{}".format(from_dt.strftime(format2), from_dt.strftime(format2))

        data = {"frontCate": 4000,
            "tag": "",
            "areaCode": "",
            "veld": "",
            "price": "all",
            "days": days,
            "q": keyword,
            "pricefrm": "",
            "priceto": "",
            "actfrm": from_dt.strftime(format1),
            "actto": from_dt.strftime(format1),
        }
        r = requests.post(url=url, data=data, verify=False)
        content = r.content.decode("utf-8")
        root = etree.HTML(content)
        ul_node = root.find('.//ul[@class="node-list"]')
        if ul_node is None:
            print("no shows for {} at {}".format(keyword, from_dt))
            return None
        li_nodes = ul_node.findall('li')
        if len(li_nodes) > 1:
            print("need investigate - {} has multiple shows at {}".format(keyword, from_dt))
            return None
        title_node = li_nodes[0].find('.//div[@class="info"]//h3[@class="title"]/a')
        relative_url = title_node.get("href")
        absolute_url = "http://www.xishiqu.com" + relative_url
        act_code = self.get_act_code(absolute_url)
        event_id = self.get_event_id_by_time(act_code, from_dt)
        return event_id

    def get_event_mapping(self):
        concerts = self.db.concert.aggregate([
            {"$unwind": "$performs"},
        ])
        for concert in concerts:
            name = concert["name"]
            timestamp = concert["performs"]["start_time"]
            performid = concert["performs"]["performid"]
            existing = self.db.xishiqu_mapping.find({"performid": performid}).count()
            if existing > 0:
                continue
            show_dt = datetime.datetime.fromtimestamp(timestamp)
            actor_str = concert["actors"]
            venue_str = concert["venue"]
            actor = actor_str.split(":")[-1].strip()
            print(name)
            event_id = None
            if actor:
                keyword = actor
                event_id = self.get_event_id(show_dt, keyword)
                if event_id is not None:
                    mapping = {"performid": performid,
                        "eventid": event_id}
                    self.db.xishiqu_mapping.insert_one(mapping)
                    continue

            keywords = lib.utils.get_keyword(name)
            for keyword in keywords:
                event_id = self.get_event_id(show_dt, keyword)
                if event_id:
                    mapping = {"performid": performid,
                        "eventid": event_id}
                    self.db.xishiqu_mapping.insert_one(mapping)
                    break

    def get_event_tickets(self, event_id):
        url_patt = "http://www.xishiqu.com/api/event/tickets?eventId={}&pageCur={}&pageSize=5&faceKey="
        curr_page = 1
        result = []
        while True:
            url = url_patt.format(event_id, curr_page)
            r = requests.get(url, verify=False)
            content = r.content.decode("utf-8")
            data = json.loads(content)
            if data["code"] == "000":
                print("error with {}".format(url))
                continue
            items = data["result"]["list"]
            for item in items:
                pre_sale = item["isPreSale"] == "1"
                result.append({
                    "ticketid": item["ticketsId"],
                    "service": item["deliveryTime"]["serviceName"],
                    "seller": item["seller"],
                    "face_price": float(item["facePrice"]),
                    "deal_price": float(item["dealPrice"]),
                    "amount": item["leftQuantity"],
                    "express": item["expressType"],
                    "section": item["sectionName"],
                    "is_series": item["isSeries"],
                    "pre_sale": pre_sale,
                })
            total = data["result"]["total"]
            fetched = len(items) + 5*(curr_page-1)
            if fetched >= total:
                break
            curr_page += 1
        return result

    def get_act_code(self, url):
        r = requests.get(url, verify=False)
        content = r.content.decode("utf-8")
        root = etree.HTML(content)
        node = root.find('.//div[@class="info-box"]')
        act_code = node.get("data-act-code")
        return act_code

    def get_event_id_by_time(self, act_code, dt):
        date_str = dt.strftime("%m-%d %H:%M")
        event_url = "http://www.xishiqu.com/api/event/eventList?actCode={}".format(act_code)
        r = requests.get(event_url, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        for item in data["result"]:
            events = item["timeList"]
            for event in events:
                if re.match(date_str, event["title"]):
                    return event["eventId"]

    def get_perform_event_ids(self, act_code):
        event_url = "http://www.xishiqu.com/api/event/eventList?actCode={}".format(act_code)
        r = requests.get(event_url, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        result = []
        for item in data["result"]:
            events = item["timeList"]
            event_ids = list(map(lambda x: x["eventId"], events))
            result.extend(event_ids)
        return result

    def get_perform_tickets(self, url):
        act_code = self.get_act_code(url)
        event_ids = self.get_perform_event_ids(act_code)
        result = []
        for event_id in event_ids:
            tickets = self.get_event_tickets(event_id)
            result.extend(tickets)
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

    def get_events_asks(self):
        events = self.db.concert.aggregate([
            {"$unwind": "$performs"},
            {"$lookup": {"from": "xishiqu_mapping", "localField": "performs.performid", "foreignField": "performid", "as": "xishiqu_mapping"}},
            {"$match": {"xishiqu_mapping": {"$ne": []}}},
            {"$unwind": "$xishiqu_mapping"},
        ])
        for event in events:
            eventid = event["xishiqu_mapping"]["eventid"]
            performid = event["performs"]["performid"]
            tickets = self.get_event_tickets(eventid)
            now = datetime.datetime.now()
            for ticket in tickets:
                matched = self.find_std_price(performid, ticket["face_price"], ticket["section"])
                if matched is None:
                    continue
                existing = self.db.xishiqu_ask.find({"ticketid": ticket["ticketid"]}).count()
                if existing > 0:
                    continue
                item = {
                    "ticketid": ticket["ticketid"],
                    "priceid": matched["priceid"],
                    "ask": ticket["deal_price"],
                    "amount": ticket["amount"],
                    "service": ticket["service"],
                    "seller": ticket["seller"],
                    "express": ticket["express"],
                    "section": ticket["section"],
                    "is_series": ticket["is_series"],
                    "when_created": now,
                }
                self.db.xishiqu_ask.insert_one(item)
                print("insert one price")

    def get_asks_by_priceid(self, priceid):
        items = self.db.xishiqu_ask.find({"priceid": priceid})
        result = []
        for item in items:
            result.append({
                "priceid": item["priceid"],
                "ask": item["ask"],
                "amount": item["amount"],
                "service": item["service"],
                "seller": item["seller"],
                "express": item["express"],
                "section": item["section"],
                "is_series": item["is_series"],
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
