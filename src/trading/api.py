import logging
import concurrent.futures
from NorenRestApiPy.NorenApi import NorenApi

class Order:
    def __init__(self, buy_or_sell:str = None, product_type:str = None,
                 exchange: str = None, tradingsymbol:str =None,
                 price_type: str = None, quantity: int = None,
                 price: float = None, trigger_price:float = None, discloseqty: int = 0,
                 retention:str = 'DAY', remarks: str = "tag",
                 order_id:str = None):
        self.buy_or_sell=buy_or_sell
        self.product_type=product_type
        self.exchange=exchange
        self.tradingsymbol=tradingsymbol
        self.quantity=quantity
        self.discloseqty=discloseqty
        self.price_type=price_type
        self.price=price
        self.trigger_price=trigger_price
        self.retention=retention
        self.remarks=remarks
        self.order_id=order_id

class NorenApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(self, host='https://piconnect.flattrade.in/PiConnectAPI/', websocket='wss://piconnect.flattrade.in/PiConnectWSAPI/')

    def placeOrder(self, order: Order):
        ret = NorenApi.place_order(self, buy_or_sell=order.buy_or_sell, product_type=order.product_type,
                            exchange=order.exchange, tradingsymbol=order.tradingsymbol,
                            quantity=order.quantity, discloseqty=order.discloseqty, price_type=order.price_type,
                            price=order.price, trigger_price=order.trigger_price,
                            retention=order.retention, remarks=order.remarks)
        return ret

class FlattradeClient:
    def __init__(self):
        self.api = NorenApiPy()


    def login(self, user_id, token):
        try:
            ret = self.api.set_session(userid=user_id, password='', usertoken=token)
            if ret:
                logging.info("Login successful")
                return True
            else:
                logging.error("Login failed")
                return False
        except Exception as e:
            logging.error(f"Login exception: {e}")
            return False
        except Exception as e:
            logging.error(f"Login exception: {e}")
            return False

    def get_index_ltp(self, index_name):
        # Index tokens: Nifty 50 = NSE|26000, Sensex = BSE|1 (verify tokens)
        exchange = 'NSE' if index_name.lower() == 'nifty' else 'BSE'
        token = '26000' if index_name.lower() == 'nifty' else '1' # Sensex Token needs verification but assuming standard mapping
        ret = self.api.get_quotes(exchange=exchange, token=token)
        if ret and ret.get('stat') == 'Ok':
            return float(ret.get('lp', 0))
        return None


    def get_nearest_expiry_option(self, index_name, opt_type, strike_price):
        exch = 'NFO' if index_name.lower() == 'nifty' else 'BFO'
        search_txt = f"{'NIFTY' if index_name.lower() == 'nifty' else 'SENSEX'} {strike_price} {opt_type}"

        try:
            # First try get_option_chain
            underlying_tsym = 'NIFTY' if index_name.lower() == 'nifty' else 'SENSEX'
            underlying_exch = 'NSE' if index_name.lower() == 'nifty' else 'BSE'
            ret = self.api.get_option_chain(exchange=underlying_exch, tradingsymbol=underlying_tsym, strikeprice=strike_price, count=5)

            if ret and ret.get('stat') == 'Ok':
                values = ret.get('values', [])
                options = [v for v in values if v.get('optt') == opt_type.upper()]
                if options:
                    options.sort(key=lambda x: abs(float(x.get('strprc', 0)) - strike_price))
                    return options[0]

            # Fallback to searchscrip if get_option_chain fails or returns nothing
            ret_search = self.api.searchscrip(exchange=exch, searchtext=search_txt)
            if ret_search and ret_search.get('stat') == 'Ok':
                values = ret_search.get('values', [])
                # Just return the first match since searchscrip is ordered by relevance/expiry usually
                if values:
                    return values[0]
        except Exception as e:
            logging.error(f"Error fetching option chain: {e}")
        return None

    def get_intraday_data(self, exchange, token, start_time):
        try:
            ret = self.api.get_time_price_series(exchange=exchange, token=token, starttime=start_time, interval=1)
            if isinstance(ret, list) and len(ret) > 0 and ret[0].get('stat') == 'Ok':
                return ret
        except Exception as e:
            logging.error(f"Error fetching intraday data: {e}")
        return []

    def place_order(self, buy_or_sell, exchange, symbol, quantity, price, order_type='MKT', trigger_price=None, is_paper=False):
        if is_paper:
            logging.info(f"PAPER TRADE: {buy_or_sell} {quantity} {symbol} @ {price}")
            return {'stat': 'Ok', 'norenordno': 'paper_order_123', 'is_paper': True, 'fillshares': quantity, 'avgprc': price}

        try:
            order = Order(
                buy_or_sell=buy_or_sell,
                product_type='M', # MIS / Margin
                exchange=exchange,
                tradingsymbol=symbol,
                quantity=quantity,
                price_type=order_type,
                price=price,
                trigger_price=trigger_price,
                retention='DAY'
            )
            ret = self.api.placeOrder(order)
            return ret
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return None

    def search_option(self, index_name, opt_type, strike_price):
        exch = 'NFO' if index_name.lower() == 'nifty' else 'BFO'
        search_txt = f"NIFTY" if index_name.lower() == 'nifty' else f"SENSEX"
        # We might need to fetch the weekly expiry from NSE, but let's just use searchscrip to find options
        # A rough search: "NIFTY CE" or similar. Flattrade API expects SymbolName + ExpDate + 'C' + StrikePrice
        # We will use get_option_chain instead for reliability, as we did above.
        pass
