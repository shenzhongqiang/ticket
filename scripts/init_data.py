import argparse
import pymongo
import lib.damai
import lib.xishiqu

def clean():
    client = pymongo.MongoClient()
    db = client["ticket"]
    db.concert.drop()
    db.std_price.drop()
    db.price_status.drop()
    db.xishiqu_mapping.drop()
    db.xishiqu_ask.drop()

def load_damai():
    inst = lib.damai.Damai()
    inst.get_concerts_from_web()
    inst.update_concerts_sale_status()
    inst.get_concerts_price_list_from_web()

def load_xishiqu():
    inst = lib.xishiqu.Xishiqu()
    inst.get_event_mapping()
    inst.get_events_asks()

clean()
load_damai()
load_xishiqu()
