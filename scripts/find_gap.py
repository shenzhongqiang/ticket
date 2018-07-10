import pandas as pd
import pymongo
from lib.xishiqu import Xishiqu
from lib.damai import Damai
from lib.motianlun import Motianlun

def find_min_ask(asks):
    result = sorted(asks, key=lambda x: x["ask"])
    return result[0]

def find_max_ask(asks):
    result = sorted(asks, key=lambda x: x["ask"], reverse=True)
    return result[0]

def sell_at_xishiqu():
    damai_inst = Damai()
    xishiqu_inst = Xishiqu()
    motianlun_inst = Motianlun()
    std_price_items = damai_inst.get_concerts_tickets_from_db("insale")

    result = []
    df = pd.DataFrame(columns=["concert_name", "priceid", "best_buy", "best_sell", "comm"])
    for item in std_price_items:
        concert_name = item["concert_name"]
        priceid = item["priceid"]
        xi_asks = xishiqu_inst.get_asks_by_priceid(priceid)
        mo_asks = motianlun_inst.get_asks_by_priceid(priceid)
        if len(xi_asks) == 0:
            continue
        std_price = item["price"]
        has_ticket = item["has_ticket"]
        if not has_ticket and len(mo_asks) == 0:
            continue
        best_buy = None
        if not has_ticket:
            ticket = find_min_ask(mo_asks)
            best_buy = ticket["ask"]
        elif len(mo_asks) == 0:
            best_buy = std_price
        else:
            mo_ticket = find_min_ask(mo_asks)
            mo_ask = mo_ticket["ask"]
            best_buy = min(mo_ask, std_price)

        xi_ask = find_min_ask(xi_asks)
        best_sell = xi_ask["ask"]
        comm = Xishiqu.get_commission(best_sell)
        df.loc[len(df)] = [concert_name, priceid, best_buy, best_sell, comm]

    df["profit"] = df["best_sell"] - df["comm"] - df["best_buy"]
    df["profit_perc"] = df["profit"] / df["best_buy"]
    print(df[df.best_buy < 500].sort_values(["profit"]))

sell_at_xishiqu()
