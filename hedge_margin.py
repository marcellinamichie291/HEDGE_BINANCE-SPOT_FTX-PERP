import math
import json
import ccxt
import time
import os
import sys

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

################################################################################
ASSETS_TO_HEDGE = ['FIRO']

G_MARGIN_exchange_n=''
################################################################################

class hedge_margin:

    def __init__(self, COIN):
        global G_MARGIN_exchange_n
        with open('settings.json', 'r') as f:
            json_obj = json.load(f)
            
        self.COIN = COIN
        self.max_time_order_sec = 30

        self.SPOT_exchange_n = json_obj['exchange_name']
        self.MARGIN_exchange_n = json_obj['margin_exchange_name']
        G_MARGIN_exchange_n = self.MARGIN_exchange_n
        
        self.API_KEY = json_obj['API_KEY']
        self.API_SECRET = json_obj['API_SECRET']
        self.F_API_KEY = json_obj['M_API_KEY']
        self.F_API_SECRET = json_obj['M_API_SECRET']

        if self.SPOT_exchange_n.lower() == 'binance':
            self.spot_exchange = ccxt.binance({
                'apiKey': self.API_KEY,
                'secret': self.API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                },
            })
        
        if self.MARGIN_exchange_n.lower() == 'binance':
            self.MARGIN_exchange = ccxt.binance({
                'apiKey': self.F_API_KEY,
                'secret': self.F_API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'margin',
                    "fetchBalance": "margin",
                },
            })

        self.PAIR = f'{COIN}/USDT'
        self.MARGIN_PAIR = f'{COIN}/BUSD'

        self.spot_exchange.verbose = False  # debug output
        self.markets = self.spot_exchange.load_markets()
        self.market = self.spot_exchange.market(self.PAIR)
        self.balance = self.spot_exchange.fetch_balance()
        

        self.f_markets = self.MARGIN_exchange.load_markets()
        self.f_market = self.MARGIN_exchange.market(self.MARGIN_PAIR)
        params={}
        self.nb_digits_after_point = self.f_market['precision']['amount']
        self.min_amount_COIN = self.f_market['limits']['amount']['min']

        self.COIN_TOTAL = float(self.balance['total'][self.COIN])

        margin_iso = self.MARGIN_exchange.sapi_get_margin_isolated_account()

        for asset in margin_iso['assets']:
            if asset['symbol']==self.MARGIN_PAIR.replace('/',''):
                self.AMOUNT_COIN_BORROWED = float(asset['baseAsset']['borrowed'])
                self.MARGIN_POSITION_SIZE = float(asset['baseAsset']['netAsset'])
                self.MARGIN_AMOUNT_BUSD = float(asset['quoteAsset']['netAsset'])
        
        print(f"Borrowed quantity on margin account on {self.MARGIN_exchange_n} : {self.AMOUNT_COIN_BORROWED}")
        print(f"Position size on margin account on {self.MARGIN_exchange_n} : {self.MARGIN_POSITION_SIZE}  (negative for short)")
        if (self.MARGIN_POSITION_SIZE>0.0001):
            print('Positive position, but it should be negative or 0, something is wrong.')
            sys.exit()
        print(f"Margin amount of BUSD on {self.MARGIN_exchange_n} : {self.MARGIN_AMOUNT_BUSD}")
        print(f"Necessary Margin amount of BUSD on {self.MARGIN_exchange_n} : {2.0*self.COIN_TOTAL*self.get_mid_price()}")
        
        print(f"{self.COIN} quantity on {self.SPOT_exchange_n}: {self.COIN_TOTAL}")
        self.BUSD_TOTAL = float(self.balance['total']['BUSD'])
        self.USDT_TOTAL = float(self.balance['total']['USDT'])
        print(f"BUSD quantity on {self.MARGIN_exchange_n} : {self.BUSD_TOTAL}")
        print(f"USDT quantity on {self.MARGIN_exchange_n} : {self.USDT_TOTAL}")

        pass

    def get_MARGIN_AMOUNT_BUSD(self):
        margin_iso = self.MARGIN_exchange.sapi_get_margin_isolated_account()
        for asset in margin_iso['assets']:
            if asset['symbol']==self.MARGIN_PAIR.replace('/',''):
                MARGIN_AMOUNT_BUSD = float(asset['quoteAsset']['netAsset'])
        return MARGIN_AMOUNT_BUSD 

################################################################################

    def transfer_margin_or_borrow_if_necessary(self):

        mid_price = self.get_mid_price()

        pc_diff = (2.0*self.COIN_TOTAL-self.MARGIN_AMOUNT_BUSD/mid_price)/(self.COIN_TOTAL)*100.0
        print(pc_diff)
        
        if pc_diff>5.0:
            print('Requiring more BUSD margin to be safe. Transferring from spot to margin in BUSD...')
            BUSD_to_transfer = abs(math.ceil((1.1*self.COIN_TOTAL-self.MARGIN_AMOUNT_BUSD/mid_price)*mid_price))+1.0
            self.MARGIN_exchange.sapi_post_margin_isolated_transfer({
                'asset': 'BUSD',
                'amount': str(BUSD_to_transfer),
                'symbol': self.MARGIN_PAIR.replace('/',''),
                'transFrom': 'SPOT',
                'transTo': 'ISOLATED_MARGIN'
                })
            print('Done.')
        else:
            print('No need to transfer more BUSD margin.')

        if (self.COIN_TOTAL-self.AMOUNT_COIN_BORROWED)/self.COIN_TOTAL*100.0>5.0:
            print(f'Borrowing more {self.COIN}...')
            currency = self.MARGIN_exchange.currency(self.COIN)
            amount = self.MARGIN_exchange.currency_to_precision(self.COIN, round(self.COIN_TOTAL-self.AMOUNT_COIN_BORROWED,self.nb_digits_after_point))
            self.MARGIN_exchange.sapi_post_margin_loan({
                'asset': currency['id'],
                'amount': amount,
                'isIsolated': 'TRUE',
                'symbol': self.MARGIN_PAIR.replace('/','')
            })
            print('Done.')
        else:
            print(f'No need to borrow more {self.COIN}.')

################################################################################

    def process(self):

        mid_price = self.get_mid_price()

        print(f"{self.COIN} short position size on {self.MARGIN_exchange_n}: {self.MARGIN_POSITION_SIZE}")
        
        qty_to_open = self.COIN_TOTAL-abs(self.MARGIN_POSITION_SIZE)
        print(f"diff: {qty_to_open}")
        qty_to_open = round(qty_to_open,self.nb_digits_after_point)
        print(f"diff rounded to allowed precision by exchange: {qty_to_open}")
        qty_to_open = float(self.MARGIN_exchange.amount_to_precision(self.MARGIN_PAIR,qty_to_open))
        print(f"quantity of {self.MARGIN_PAIR} to increase or reduce: {qty_to_open}")

        if abs(qty_to_open)<self.min_amount_COIN:
            print('no need to open short, short position is already with the wanted size')
            return None

        if qty_to_open > 0:
            print('Trying trade to increase short position...')
            coin_amt, price = self.INCREASE_SHORT_MAKER_FAST(qty_to_open)
            print('Done.')
            return None
        else :
            print('Trying trade to reduce short position...')
            coin_amt, price = self.REDUCE_SHORT_MAKER_FAST(abs(qty_to_open))
            print('Done.')
            return None

################################################################################

    def close_short_position(self):
        print('Trying trade to reduce short position...')
        qty_to_reduce = float(self.MARGIN_exchange.amount_to_precision(self.MARGIN_PAIR,round(abs(self.MARGIN_POSITION_SIZE),self.nb_digits_after_point)))
        if qty_to_reduce*self.get_mid_price()>10.5:
            coin_amt, price = self.REDUCE_SHORT_MAKER_FAST(qty_to_reduce)
        else:
            print('No need to reduce short position. Already at size 0 or close.')
        print('Done.')

################################################################################

    def repay_and_transfer_margin_to_spot_account(self):

        currency = self.MARGIN_exchange.currency(self.COIN)

        amount = self.MARGIN_exchange.currency_to_precision(self.COIN, self.AMOUNT_COIN_BORROWED)

        if self.AMOUNT_COIN_BORROWED*self.get_mid_price()>1.0:
            print(f'Repaying borrowed {self.COIN}...')
            self.MARGIN_exchange.sapi_post_margin_repay({
                'asset': currency['id'],
                'amount': amount,
                'isIsolated': 'TRUE',
                'symbol': self.MARGIN_PAIR.replace('/','')
                })
            print('Done.')

        self.MARGIN_AMOUNT_BUSD = self.get_MARGIN_AMOUNT_BUSD()
        if self.MARGIN_AMOUNT_BUSD>0.2:
            print('Transfering BUSD from margin to spot...')
            BUSD_to_transfer = abs(self.MARGIN_AMOUNT_BUSD)
            is_error=True
            while is_error:
                try:
                    self.MARGIN_exchange.sapi_post_margin_isolated_transfer({
                        'asset': 'BUSD',
                        'amount': str(self.MARGIN_exchange.currency_to_precision('BUSD',BUSD_to_transfer)),
                        'symbol': self.MARGIN_PAIR.replace('/',''),
                        'transFrom': 'ISOLATED_MARGIN',
                        'transTo': 'SPOT'
                        })
                    is_error=False
                except Exception as e:
                    BUSD_to_transfer = round(BUSD_to_transfer,2)-0.02
                    print(f'Amount to transfer is too high, reducing by 0.1 BUSD, new amount: {BUSD_to_transfer}')
                    print(str(e))
                    time.sleep(1)
            print('Done.')


################################################################################   
    def close_session(self):
        pass

################################################################################
    def get_mid_price(self):
        orderbook = self.spot_exchange.fetch_order_book(self.PAIR)
        ask = orderbook['asks'][0][0]
        bid = orderbook['bids'][0][0]
        mid_price = (ask+bid)/2.0
        return mid_price

    def get_already_open_quantity(self):
        qty = 0.0
        response = self.MARGIN_exchange.fetch_positions(symbols=[self.MARGIN_PAIR])
        for res in response:
            if res['side']=='short':
                if abs(float(res['contracts']))>0.0:
                    qty = abs(float(res['contracts']))
        return qty

################################################################################
    def INCREASE_SHORT_MAKER_FAST(self, COIN_amount):

        max_limit_orders_to_try = 20

        params = {
            'type': 'margin',
            'isIsolated': 'TRUE'
        }
        side = 'sell'
        typee = 'limit'
        market_buy_counter = 0
        processed = False
        while not processed:
            orderbook = self.MARGIN_exchange.fetch_order_book(self.MARGIN_PAIR)
            ask = orderbook['asks'][0][0]
            bid = orderbook['bids'][0][0]
            price = max(ask, bid)
            order = self.MARGIN_exchange.create_order(self.MARGIN_PAIR.replace('/',''), typee, side, COIN_amount, price, params=params)
            print(order)
            idd = order['id']
            t0 = time.time()
            while True:
                time.sleep(0.1)
                order = self.MARGIN_exchange.fetchOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
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
                            self.MARGIN_exchange.cancelOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
                            print("order has been canceled")
                        except:
                            print("order failed to be canceled")
                            pass
                        self.MARGIN_exchange.create_order(self.MARGIN_PAIR.replace('/',''), 'market', side, COIN_amount, params=params)
                        print("market buy done")
                        processed = True
                        break
                    order = self.MARGIN_exchange.fetchOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
                    if order['status'] == 'closed':
                        processed = True
                        break
                    if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                        break
                    try:
                        self.MARGIN_exchange.cancelOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
                        print(f"order has been canceled ({market_buy_counter}/{max_limit_orders_to_try})")
                    except:
                        print("order failed to be canceled")
                        pass
        return COIN_amount, price

################################################################################
    def REDUCE_SHORT_MAKER_FAST(self, COIN_amount):

        max_limit_orders_to_try = 20

        params = {
            'type': 'margin',
            'isIsolated': 'TRUE'
        }
        side = 'buy'
        typee = 'limit'
        market_buy_counter = 0
        processed = False
        while not processed:
            orderbook = self.MARGIN_exchange.fetch_order_book(self.MARGIN_PAIR)
            ask = orderbook['asks'][0][0]
            bid = orderbook['bids'][0][0]
            price = min(ask, bid)
            order = self.MARGIN_exchange.create_order(self.MARGIN_PAIR.replace('/',''), typee, side, COIN_amount, price, params=params)
            print(order)
            idd = order['id']
            t0 = time.time()
            while True:
                time.sleep(0.1)
                order = self.MARGIN_exchange.fetchOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
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
                            self.MARGIN_exchange.cancelOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
                            print(f"order has been canceled")
                        except:
                            print("order failed to be canceled")
                            pass
                        self.MARGIN_exchange.create_order(self.MARGIN_PAIR.replace('/',''), 'market', side, COIN_amount, params=params)
                        print("market buy done")
                        processed = True
                        break
                    order = self.MARGIN_exchange.fetchOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
                    if order['status'] == 'closed':
                        processed = True
                        break
                    if order['status'] == 'canceled' or order['status'] == 'expired' or order['status'] == 'EXPIRED':
                        break
                    try:
                        self.MARGIN_exchange.cancelOrder(idd, self.MARGIN_PAIR.replace('/',''), params=params)
                        print(f"order has been canceled ({market_buy_counter}/{max_limit_orders_to_try})")
                    except:
                        print("order failed to be canceled")
                        pass
        return COIN_amount, price

################################################################################
############################### MAIN ###########################################

if __name__ == "__main__":

    for asset in ASSETS_TO_HEDGE:
        # try:
        hedger = hedge_margin(asset)
        hedger.transfer_margin_or_borrow_if_necessary()
        hedger.process()
        hedger.close_session()
        del hedger
        # except ccxt.errors.BadSymbol as e:
        #     print(f"error: ccxt.errors.BadSymbol: {G_MARGIN_exchange_n} does not have market symbol {asset}-PERP")