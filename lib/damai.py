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

    def get_concert_from_web(self):
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
            for perform in performs:
                performid = perform["performid"]
                existing = self.db.concert.find({"projectid": projectid, "performid": performid}).count()
                print(projectid, performid, existing)
                if existing > 1:
                    err = "damai concert project {} perform {} has {} records".format(projectid, performid, existing)
                    raise Exception(err)
                if existing == 1:
                    continue
                concert = {
                    "projectid": projectid,
                    "performid": performid,
                    "actors": actors,
                    "cityname": cityname,
                    "name": name,
                    "venue": venue,
                    "venuecity": venuecity,
                    "start_time": perform["start_time"],
                    "show_datetime": perform["show_datetime"],
                    "show_weekday": perform["show_weekday"],
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
        concerts = self.db.concert.find({"source": "damai"}, {"projectid": 1, "performid": 1})
        for concert in concerts:
            projectid = concert["projectid"]
            performid = concert["performid"]
            self.get_price_list_from_web(projectid, performid)

    def get_concerts_from_db(self):
        items = self.db.concert.find()
        for item in items:
            print(item)

    def get_concert_tickets_from_db(self, performid):
        items = self.db.price_list.find({"performid": performid})
        for item in items:
            print(item)
