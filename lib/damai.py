import datetime
import re
import json
import requests
import pymongo

class Damai(object):
    def __init__(self):
        client = pymongo.MongoClient()
        self.db = client.ticket

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
            existing = self.db.price_list.find({"priceid": priceid}).count()
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
                self.db.price_list.insert_one(price)
                print("find new price from web")

            now = datetime.datetime.now()
            price_status = {
                "priceid": priceid,
                "has_ticket": has_ticket,
                "timestamp": now
            }
            self.db.price_status.insert_one(price_status)

    def get_concerts_price_list_from_web(self):
        concerts = self.db.concert.aggregate([
            {"$unwind": "$performs"},
            {"$addFields": {"performid": "$performs.performid"}},
            {"$project": {"projectid": 1, "performid": 1}}
        ])
        for concert in concerts:
            print(concert)
            projectid = concert["projectid"]
            performid = concert["performid"]
            self.get_price_list_from_web(projectid, performid)

    def get_concerts_from_db(self):
        items = self.db.concert.find()
        for item in items:
            print(item)

    def get_concert_tickets_from_db(self, performid):
        items = self.db.price_list.aggregate([
            {"$match": {"performid": performid}},
            {"$lookup": {"from": "price_status", "localField": "priceid", "foreignField": "priceid", "as": "price_status"}}
        ])
        result = []
        for item in items:
            pstatus_inorder = sorted(item["price_status"], key=lambda x: x["timestamp"], reverse=True)
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

    def get_concerts_tickets_from_db(self):
        items = self.db.concert.aggregate([
            {"$unwind": "$performs"},
        ])
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
                print(concert_name, actors, venue, ticket_name, price, has_ticket)
