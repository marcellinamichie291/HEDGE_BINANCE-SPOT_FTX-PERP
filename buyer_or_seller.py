import math
import json
import ccxt
import time
import os
import sys

class buyer_or_seller:
    def __init__(self, COIN, wanted_quantity_in_COIN=0):
            
            self.COIN = COIN
            self.wanted = wanted_quantity_in_COIN
            self.max_time_order_sec = 20

            with open('settings.json', 'r') as f:
                json_obj = json.load(f)

            self.SPOT_exchange_n = json_obj['exchange_name']
            self.API_KEY = json_obj['API_KEY']
            self.API_SECRET = json_obj['API_SECRET']

            if self.SPOT_exchange_n.lower() == 'binance':
                self.spot_exchange = ccxt.binance({
                    'apiKey': self.API_KEY,
                    'secret': self.API_SECRET,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'spot',
                    },
                })

            self.PAIR = f'{COIN}/BUSD'

            self.spot_exchange.verbose = False  # debug output
            self.markets = self.spot_exchange.load_markets()
            self.market = self.spot_exchange.market(self.PAIR)
            self.balance = self.spot_exchange.fetch_balance()

            self.COIN_total = float(self.balance['total'][self.COIN])

################################################################################
    def BUY_SPOT_MAKER_FAST(self, COIN_amount):

        max_limit_orders_to_try = 40

        params = {
            'type': 'limit_maker'
        }
        side = 'buy'
        typee = 'limit'
        market_buy_counter = 0
        processed = False
        while not processed:
            orderbook = self.spot_exchange.fetch_order_book(self.PAIR)
            ask = orderbook['asks'][0][0]
            bid = orderbook['bids'][0][0]
            price = min(ask, bid)
            order = self.spot_exchange.create_order(self.PAIR, typee, side, COIN_amount, price, params)
            print(order)
            idd = order['id']
            t0 = time.time()
            while True:
                time.sleep(0.1)
                order = self.spot_exchange.fetchOrder(idd, self.PAIR, params={})
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
                            self.spot_exchange.cancelOrder(idd, self.PAIR, params={})
                            print("order has been canceled")
                        except:
                            print("order failed to be canceled")
                            pass
                        self.spot_exchange.create_order(self.PAIR, 'market', side, COIN_amount, params={})
                        print("market buy done")
                        processed = True
                        break
                    order = self.spot_exchange.fetchOrder(idd, self.PAIR, params={})
                    if order['status'] == 'closed':
                        processed = True
                        break
                    if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                        break
                    try:
                        self.spot_exchange.cancelOrder(idd, self.PAIR, params={})
                        print(f"order has been canceled ({market_buy_counter}/{max_limit_orders_to_try})")
                    except:
                        print("order failed to be canceled")
                        pass
        return COIN_amount, price

################################################################################
    def SELL_SPOT_MAKER_FAST(self, COIN_amount):

        max_limit_orders_to_try = 40

        params = {
            'type': 'limit_maker'
        }
        side = 'sell'
        typee = 'limit'
        market_buy_counter = 0
        processed = False
        while not processed:
            orderbook = self.spot_exchange.fetch_order_book(self.PAIR)
            ask = orderbook['asks'][0][0]
            bid = orderbook['bids'][0][0]
            price = max(ask, bid)
            order = self.spot_exchange.create_order(self.PAIR, typee, side, COIN_amount, price, params)
            print(order)
            idd = order['id']
            t0 = time.time()
            while True:
                time.sleep(0.1)
                order = self.spot_exchange.fetchOrder(idd, self.PAIR, params={})
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
                            self.spot_exchange.cancelOrder(idd, self.PAIR, params={})
                            print("order has been canceled")
                        except:
                            print("order failed to be canceled")
                            pass
                        self.spot_exchange.create_order(self.PAIR, 'market', side, COIN_amount, params={})
                        print("market buy done")
                        processed = True
                        break
                    order = self.spot_exchange.fetchOrder(idd, self.PAIR, params={})
                    if order['status'] == 'closed':
                        processed = True
                        break
                    if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                        break
                    try:
                        self.spot_exchange.cancelOrder(idd, self.PAIR, params={})
                        print(f"order has been canceled ({market_buy_counter}/{max_limit_orders_to_try})")
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
################################################################################

    def process(self):
        diff = self.wanted - self.COIN_total

        diff_pc = diff/self.wanted*100.0

        if diff_pc<-3.0:
            qty = self.spot_exchange.amount_to_precision(self.PAIR,abs(diff))
            self.SELL_SPOT_MAKER_FAST(qty)
        elif diff>3.0:
            qty = float(self.spot_exchange.amount_to_precision(self.PAIR,abs(diff)))
            self.BUY_SPOT_MAKER_FAST(qty)
        else:
            print(f'Not enough difference in {self.PAIR}, no need to rebalance (should be more than 3% in abs)')

################################################################################

    def sell_all(self):
        if self.COIN_total*self.get_mid_price() > 10.5:
            qty = self.spot_exchange.amount_to_precision(self.PAIR,abs(self.COIN_total))
            self.SELL_SPOT_MAKER_FAST(qty)

################################################################################