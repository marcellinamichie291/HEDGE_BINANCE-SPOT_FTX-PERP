import math
import json
import ccxt
import time
import os
import sys

################################################################################
ASSETS_TO_HEDGE = ['AVAX']

################################################################################

class hedge:

    def __init__(self, COIN):
        with open('settings.json', 'r') as f:
            json_obj = json.load(f)

        self.max_time_order_sec = 10

        SPOT_exchange_n = json_obj['exchange_name']
        FUT_exchange_n = json_obj['futures_exchange_name']
        
        self.API_KEY = json_obj['API_KEY']
        self.API_SECRET = json_obj['API_SECRET']
        self.F_API_KEY = json_obj['F_API_KEY']
        self.F_API_SECRET = json_obj['F_API_SECRET']

        if SPOT_exchange_n.lower() == 'binance':
            self.spot_exchange = ccxt.binance({
                'apiKey': self.API_KEY,
                'secret': self.API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                },
            })
        
        if FUT_exchange_n.lower() == 'ftx':
            self.fut_exchange = ccxt.ftx({
                'apiKey': self.F_API_KEY,
                'secret': self.F_API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'futures',
                },
            })

        self.PAIR = f'{COIN}/USDT'
        self.fut_PAIR = f'{COIN}-PERP'

        self.spot_exchange.verbose = False  # debug output
        self.markets = self.spot_exchange.load_markets()
        self.market = self.spot_exchange.market(self.PAIR)
        self.balance = self.spot_exchange.fetch_balance()
        self.COIN_TOTAL = float(self.balance['total'][COIN])
        print(f"{COIN} quantity on {SPOT_exchange_n}: {self.COIN_TOTAL}")

        self.f_markets = self.fut_exchange.load_markets()
        self.f_market = self.fut_exchange.market(self.fut_PAIR)
        self.f_balance = self.fut_exchange.fetch_balance()
        prec = self.f_market['precision']['amount']
        nb_digits_after_point = int(-1*math.log10(prec))
        self.min_amount_COIN = self.f_market['limits']['amount']['min']
        self.USD_TOTAL = float(self.f_balance['total']['USD'])
        print(f"USD quantity on {FUT_exchange_n} : {self.USD_TOTAL}")

        mid_price = self.get_mid_price()

        self.qtty_in_short = self.get_already_open_quantity()
        print(f"{COIN} short position size on {FUT_exchange_n}: {self.qtty_in_short}")
        
        qty_to_open = self.COIN_TOTAL-self.qtty_in_short
        print(qty_to_open)
        qty_to_open = round(qty_to_open,nb_digits_after_point)
        print(qty_to_open)
        qty_to_open = float(self.fut_exchange.amount_to_precision(self.fut_PAIR,qty_to_open))
        print(f"quantity of {self.fut_PAIR} to increase or reduce: {qty_to_open}")

        if abs(qty_to_open)<self.min_amount_COIN:
            print('no need to open short, short position is already with the wanted size')
            return None

        if ((self.COIN_TOTAL-self.qtty_in_short)*mid_price/self.USD_TOTAL*100.0>=2.0):
            print('not enough USDT on futures exchange to open the Hedge short')
            return None

        if qty_to_open > 0:
            print('Trying trade to increase short position...')
            coin_amt, price = self.INCREASE_SHORT_MAKER_FAST(qty_to_open)
            print('Done')
            return None
        else :
            print('Trying trade to reduce short position...')
            coin_amt, price = self.REDUCE_SHORT_MAKER_FAST(abs(qty_to_open))
            print('Done')
            return None

################################################################################
    def INCREASE_SHORT_MAKER_FAST(self, COIN_amount):

        max_limit_orders_to_try = 10

        params = {
            'postOnly': True
        }
        side = 'sell'
        typee = 'limit'
        market_buy_counter = 0
        processed = False
        while not processed:
            orderbook = self.fut_exchange.fetch_order_book(self.fut_PAIR)
            ask = orderbook['asks'][0][0]
            bid = orderbook['bids'][0][0]
            price = max(ask, bid)
            order = self.fut_exchange.create_order(self.fut_PAIR, typee, side, COIN_amount, price, params)
            print(order)
            idd = order['id']
            t0 = time.time()
            while True:
                time.sleep(0.1)
                order = self.fut_exchange.fetchOrder(idd, self.fut_PAIR, params={})
                t1 = time.time()
                clock = t1-t0
                if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                    break
                if order['status'] == 'closed':
                    processed = True
                    break
                if (clock > self.max_time_order_sec):
                    market_buy_counter = market_buy_counter+1
                    if market_buy_counter >= max_limit_orders_to_try:
                        print("too much order failed, doing market buy")
                        try:
                            self.fut_exchange.cancelOrder(idd, self.fut_PAIR, params={})
                            print("order has been canceled")
                        except:
                            print("order failed to be canceled")
                            pass
                        self.fut_exchange.create_order(self.fut_PAIR, 'market', side, COIN_amount, params={})
                        print("market buy done")
                        processed = True
                        break
                    order = self.fut_exchange.fetchOrder(idd, self.fut_PAIR, params={})
                    if order['status'] == 'closed':
                        processed = True
                        break
                    if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                        break
                    try:
                        self.fut_exchange.cancelOrder(idd, self.fut_PAIR, params={})
                        print("order has been canceled")
                    except:
                        print("order failed to be canceled")
                        pass
        return COIN_amount, price

################################################################################
    def REDUCE_SHORT_MAKER_FAST(self, COIN_amount):

        max_limit_orders_to_try = 10

        params = {
            'postOnly': True
        }
        side = 'buy'
        typee = 'limit'
        market_buy_counter = 0
        processed = False
        while not processed:
            orderbook = self.fut_exchange.fetch_order_book(self.fut_PAIR)
            ask = orderbook['asks'][0][0]
            bid = orderbook['bids'][0][0]
            price = min(ask, bid)
            order = self.fut_exchange.create_order(self.fut_PAIR, typee, side, COIN_amount, price, params)
            print(order)
            idd = order['id']
            t0 = time.time()
            while True:
                time.sleep(0.1)
                order = self.fut_exchange.fetchOrder(idd, self.fut_PAIR, params={})
                t1 = time.time()
                clock = t1-t0
                if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                    break
                if order['status'] == 'closed':
                    processed = True
                    break
                if (clock > self.max_time_order_sec):
                    market_buy_counter = market_buy_counter+1
                    if market_buy_counter >= max_limit_orders_to_try:
                        print("too much order failed, doing market buy")
                        try:
                            self.fut_exchange.cancelOrder(idd, self.fut_PAIR, params={})
                            print("order has been canceled")
                        except:
                            print("order failed to be canceled")
                            pass
                        self.fut_exchange.create_order(self.fut_PAIR, 'market', side, COIN_amount, params={})
                        print("market buy done")
                        processed = True
                        break
                    order = self.fut_exchange.fetchOrder(idd, self.fut_PAIR, params={})
                    if order['status'] == 'closed':
                        processed = True
                        break
                    if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                        break
                    try:
                        self.fut_exchange.cancelOrder(idd, self.fut_PAIR, params={})
                        print("order has been canceled")
                    except:
                        print("order failed to be canceled")
                        pass
        return COIN_amount, price
################################################################################

    def get_mid_price(self):
        orderbook = self.spot_exchange.fetch_order_book(self.PAIR)
        ask = orderbook['asks'][0][0]
        bid = orderbook['bids'][0][0]
        mid_price = (ask+bid)/2.0
        return mid_price

    def get_already_open_quantity(self):
        qty = 0.0
        response = self.fut_exchange.fetch_positions(symbols=[self.fut_PAIR])
        for res in response:
            if res['side']=='short':
                if res['contracts']>0.0:
                    qty = res['contracts']
        return qty


################################################################################
############################### MAIN ###########################################

if __name__ == "__main__":

    for asset in ASSETS_TO_HEDGE:
        hedger = hedge(asset)
