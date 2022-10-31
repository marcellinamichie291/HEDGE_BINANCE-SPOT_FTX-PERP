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
ASSETS_TO_UNSET = ['FRONT','FIRO'] # asset name

################################################################################

if __name__ == "__main__":

    for asset in ASSETS_TO_UNSET:

        # unset hedging
        print(f'{asset}: Unsetting Hedge (short position) on margin account if necessary...')
        hedger = hedge_margin(asset)
        hedger.close_short_position()
        hedger.repay_and_transfer_margin_to_spot_account()
        hedger.close_session()
        del hedger
        print('Done.')

        # sell all asset
        print(f'{asset}: Selling spot asset if necessary...')
        seller = buyer_or_seller(asset)
        seller.sell_all()
        del seller
        print('Done.')

        # re-balance BUSD and USDT
        print(f'{asset}: Rebalancing USDT and BUSD to equal amounts if necessary.')
        reba = rebalancer()
        reba.re_balance()
        del reba
        print('Done.')