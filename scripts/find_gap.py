import pandas as pd
import pymongo
from lib.xishiqu import Xishiqu
from lib.damai import Damai

def find_best():
    damai_inst = Damai()
    xishiqu_inst = Xishiqu()
    std_price_items = damai_inst.get_concerts_tickets_from_db("insale")

    result = []
    df = pd.DataFrame(columns=["concert_name", "priceid", "std_price", "ask_price", "comm"])
    for item in std_price_items:
        concert_name = item["concert_name"]
        priceid = item["priceid"]
        ask_items = xishiqu_inst.get_asks_by_priceid(priceid)
        std_price = item["price"]
        has_ticket = item["has_ticket"]
        if not has_ticket:
            continue

        for ask_item in ask_items:
            ask_price = ask_item["ask"]
            comm = Xishiqu.get_commission(ask_price)
            df.loc[len(df)] = [concert_name, priceid, std_price, ask_price, comm]

    df["profit"] = df["ask_price"] - df["comm"] - df["std_price"]
    df["profit_perc"] = df["profit"] / df["std_price"]
    print(df[df.std_price < 500].sort_values(["profit"]))

find_best()
