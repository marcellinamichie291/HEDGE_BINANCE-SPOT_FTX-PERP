import math
import json
import ccxt
import time
import os

################################################################################

class rebalancer:

    def __init__(self):
        with open('settings.json', 'r') as f:
            json_obj = json.load(f)
        
        self.API_KEY = json_obj['API_KEY']
        self.API_SECRET = json_obj['API_SECRET']

        self.exchange = ccxt.binance({
                        'apiKey': self.API_KEY,
                        'secret': self.API_SECRET,
                        # here enableRateLimit is important to be able to send orders as quickly as possible
                        'enableRateLimit': True,
                        'options': {
                            'defaultType': 'spot',
                        },
                    })

        self.PAIR = 'BUSD/USDT'
        self.exchange.verbose = False  # debug output
        self.markets = self.exchange.load_markets()
        self.market = self.exchange.market(self.PAIR)

        self.balance = self.exchange.fetch_balance()
        self.BUSD_total = float(self.balance['total']['BUSD'])
        self.USDT_total = float(self.balance['total']['USDT'])

################################################################################

    def re_balance(self):
        diff = self.BUSD_total - self.USDT_total

        orderbook = self.exchange.fetch_order_book(self.PAIR)
        ask = orderbook['asks'][0][0]
        bid = orderbook['bids'][0][0]

        print(diff)

        if diff>22.0:
            side = 'sell'
            typee = 'limit'
            params = {}
            amount = abs(float(self.exchange.amount_to_precision(self.PAIR, diff/2.0)))
            print(amount)
            price = min(ask, bid)
            order = self.exchange.create_order(self.PAIR, typee, side, amount, price, params)
        elif diff<-22.0:
            side = 'buy'
            typee = 'limit'
            params = {}
            amount = abs(float(self.exchange.amount_to_precision(self.PAIR, diff/2.0)))
            print(amount)
            price = max(ask, bid)
            order = self.exchange.create_order(self.PAIR, typee, side, amount, price, params)
        else:
            print(f'Not enough difference in {self.PAIR}, no need to rebalance (should be more than 22 in abs)')


################################################################################
############################### MAIN ###########################################

if __name__ == "__main__":

    reba = rebalancer()

    reba.re_balance()
