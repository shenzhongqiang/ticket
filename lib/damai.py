import datetime
import re
import json
from lxml import etree
import requests
import pymongo

class Damai(object):
    def __init__(self):
        client = pymongo.MongoClient()
        self.db = client.ticket

    def get_sale_status_from_web(self, projectid):
        url = "https://piao.damai.cn/{}.html".format(projectid)
        r = requests.get(url)
        content = r.content.decode("utf-8")
        root = etree.HTML(content)
        div_node = root.find('.//div[@id="projectAxis"]')
        status_nodes = div_node.xpath(".//div[contains(@class, 'itm-crt')]/h3")
        if len(status_nodes) == 0:
            return "unknown"
        status_node = status_nodes[0]
        text = status_node.text
        if text == "售票中":
            return "insale"
        if text == "预售/预订":
            return "presale"
        if text == "项目待定":
            return "tbd"
        if text == "演出开始":
            return "saleclosed"

    def update_concerts_sale_status(self):
        items = self.db.concert.find()
        for item in items:
            projectid = item["projectid"]
            sale_status = self.get_sale_status_from_web(projectid)
            self.db.concert.update_one({"projectid": projectid}, {"$set": {"salestatus": sale_status}})
            print("updated sale status")

    def get_performs_from_web(self, projectid):
        url = "https://piao.damai.cn/ajax/getInfo.html?projectId={}".format(projectid)
        r = requests.get(url, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        performs = data["Data"]["performs"]
        result = []
        for perform in performs:
            matched = re.search(r'(\d+)', perform["StartTime"])
            timestamp = 0
            if matched:
                timestamp = int(matched.group(1))/1000
            show_dt = datetime.datetime.fromtimestamp(timestamp)
            result.append({
                "performid": perform["PerformID"],
                "start_time": timestamp,
                "show_datetime": show_dt,
                "show_weekday": perform["ShowWeekday"],
            })
        return result

    def get_concerts_from_web(self):
        url = "https://search.damai.cn/searchajax.html"
        cty = "上海"
        ctl = "演唱会"
        data = {"keyword": "",
            "cty": cty,
            "ctl": ctl,
            "tn": "",
            "sctl": "",
            "singleChar": "",
            "order": 1
        }
        r = requests.post(url, data=data, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        total_page_num = data["pageData"]["totalPage"]
        total_result_num = data["pageData"]["totalResults"]
        items = data["pageData"]["resultData"]
        for item in items:
            projectid = item["projectid"]
            actors = item["actors"]
            cityname = item["cityname"]
            name = item["name"]
            venue = item["venue"]
            venuecity = item["venuecity"]
            performs = self.get_performs_from_web(projectid)
            existing = self.db.concert.find({"projectid": projectid}).count()
            if existing > 1:
                err = "damai concert project {} has {} records".format(projectid, existing)
                raise Exception(err)
            if existing == 1:
                continue

            concert = {
                "projectid": projectid,
                "actors": actors,
                "cityname": cityname,
                "name": name,
                "venue": venue,
                "venuecity": venuecity,
                "performs": performs,
                "source": "damai",
                "salestatus": "",
            }
            self.db.concert.insert_one(concert)
            print("find one new concert from web")

    def get_price_list_from_web(self, projectid, performid):
        url = "https://piao.damai.cn/ajax/getPriceList.html?projectId={}&performId={}".format(projectid, performid)
        r = requests.get(url, verify=False)
        content = r.content.decode("utf-8")
        data = json.loads(content)
        if data["Status"] == 404:
            return

        items = data["Data"]["list"]
        for item in items:
            has_ticket = item["Status"] == 0
            is_taopiao = item["IsTaoPiao"]
            priceid = item["PriceID"]
            existing = self.db.std_price.find({"priceid": priceid}).count()
            if existing > 1:
                err = "damai price {} has {} records".format(priceid, existing)
                raise Exception(err)

            if existing == 0:
                price = {
                    "priceid": priceid,
                    "projectid": projectid,
                    "performid": performid,
                    "price": item["SellPrice"],
                    "name": item["PriceName"],
                    "is_taopiao": is_taopiao,
                    "source": "damai",
                }
                self.db.std_price.insert_one(price)
                print("find new price from web")

            now = datetime.datetime.now()
            price_status = {
                "priceid": priceid,
                "has_ticket": has_ticket,
                "when_created": now
            }
            self.db.price_status.insert_one(price_status)

    def get_concerts_price_list_from_web(self):
        concerts = self.db.concert.aggregate([
            {"$unwind": "$performs"},
            {"$addFields": {"performid": "$performs.performid"}},
            {"$project": {"projectid": 1, "performid": 1}}
        ])
        for concert in concerts:
            projectid = concert["projectid"]
            performid = concert["performid"]
            self.get_price_list_from_web(projectid, performid)

    def get_concerts_from_db(self):
        items = self.db.concert.find()
        for item in items:
            print(item)

    def get_concert_tickets_from_db(self, performid):
        items = self.db.std_price.aggregate([
            {"$match": {"performid": performid}},
            {"$lookup": {"from": "price_status", "localField": "priceid", "foreignField": "priceid", "as": "price_status"}}
        ])
        result = []
        for item in items:
            pstatus_inorder = sorted(item["price_status"], key=lambda x: x["when_created"], reverse=True)
            price = item["price"]
            has_ticket = None
            if len(pstatus_inorder) > 0:
                has_ticket = pstatus_inorder[0]["has_ticket"]

            result.append({
                "priceid": item["priceid"],
                "price": price,
                "has_ticket": has_ticket,
                "name": item["name"],
            })
        return result

    def get_concerts_tickets_from_db(self, sale_status=None):
        items = []
        if sale_status is None:
            items = self.db.concert.aggregate([
                {"$unwind": "$performs"},
            ])
        else:
            items = self.db.concert.aggregate([
                {"$unwind": "$performs"},
                {"$match": {"salestatus": sale_status}},
            ])

        result = []
        for item in items:
            concert_name = item["name"]
            venue = item["venue"]
            actors = item["actors"]
            performid = item["performs"]["performid"]
            tickets = self.get_concert_tickets_from_db(performid)
            projectid = item["projectid"]
            for ticket in tickets:
                priceid = ticket["priceid"]
                price = ticket["price"]
                has_ticket = ticket["has_ticket"]
                ticket_name = ticket["name"]
                result.append({
                    "concert_name": concert_name,
                    "actors": actors,
                    "projectid": projectid,
                    "performid": performid,
                    "priceid": priceid,
                    "price": price,
                    "has_ticket": has_ticket,
                    "ticket_name": ticket_name
                })
        return result

    def get_performs_from_db(self):
        items = self.db.concert.aggregate([
            {"$unwind": "$performs"},
        ])
        result = []
        for item in items:
            concert_name = item["name"]
            performid = item["performs"]["performid"]
            timestamp = item["performs"]["start_time"]
            start_dt = datetime.datetime.fromtimestamp(timestamp)
            venue = item["venue"]
            actors = item["actors"]
            result.append(item)
        return result
