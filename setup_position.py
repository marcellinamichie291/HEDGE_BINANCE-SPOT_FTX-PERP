import math
import json
import ccxt
import time
import os
import sys
from hedge_margin import hedge_margin
from rebalancer_usdt_busd import rebalancer
from buyer_or_seller import buyer_or_seller

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

################################################################################
ASSETS_TO_HEDGE = [('FRONT',55),('FIRO',30)] # asset name and wanted position size

################################################################################

if __name__ == "__main__":

    for asset in ASSETS_TO_HEDGE:

        # buy the wanted quantity of asset
        print(f'{asset[0]}: Buying or selling asset if necessary...')
        buyer = buyer_or_seller(asset[0],asset[1])
        buyer.process()
        del buyer
        print('Done.')

        # set hedging
        print(f'{asset[0]}: Setting up Hedge (short position) on margin account if necessary.')
        hedger = hedge_margin(asset[0])
        hedger.transfer_margin_or_borrow_if_necessary()
        hedger.process()
        hedger.close_session()
        del hedger
        print('Done.')

        # re-balance BUSD and USDT
        print(f'{asset[0]}: Rebalancing USDT and BUSD to equal amounts if necessary.')
        reba = rebalancer()
        reba.re_balance()
        del reba
        print('Done.')