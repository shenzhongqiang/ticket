import argparse
import pymongo
import lib.damai
import lib.xishiqu
import lib.motianlun

def clean():
    client = pymongo.MongoClient()
    db = client["ticket"]
    db.concert.remove({})
    db.std_price.remove({})
    db.price_status.remove({})
    db.xishiqu_mapping.remove({})
    db.motianlun_mapping.remove({})
    db.xishiqu_ask.remove({})
    db.motianlun_ask.remove({})

def load_damai():
    inst = lib.damai.Damai()
    inst.get_concerts_from_web()
    inst.update_concerts_sale_status()
    inst.get_concerts_price_list_from_web()

def load_xishiqu():
    inst = lib.xishiqu.Xishiqu()
    inst.get_event_mapping()
    inst.get_events_asks()

def load_motianlun():
    inst = lib.motianlun.Motianlun()
    inst.get_session_mapping()
    inst.get_session_asks()

clean()
load_damai()
load_xishiqu()
load_motianlun()
