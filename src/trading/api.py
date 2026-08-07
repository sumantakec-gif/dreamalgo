import logging
import concurrent.futures
import hashlib
import requests
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
        self.last_debug_info = ""
        self.last_api_error = ""

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




    def generate_session_token(self, api_key, api_secret, auth_code):
        try:
            # Generate SHA256 hash
            hash_string = f"{api_key}{auth_code}{api_secret}"
            hashed_secret = hashlib.sha256(hash_string.encode()).hexdigest()

            payload = {
                "api_key": api_key,
                "request_code": auth_code,
                "api_secret": hashed_secret
            }

            response = requests.post("https://authapi.flattrade.in/trade/apitoken", json=payload)
            if response.status_code == 200:
                data = response.json()
                if data.get("stat") == "Ok":
                    # Flattrade returns the user ID as 'client' and session token as 'token'
                    return data.get("client"), data.get("token")
                else:
                    self.last_api_error = data.get("emsg", "Unknown Error in Token Generation")
                    return None, None
            else:
                self.last_api_error = f"HTTP {response.status_code}: {response.text}"
                return None, None
        except Exception as e:
            self.last_api_error = f"Exception in token generation: {str(e)}"
            return None, None

    def login(self, user_id, token):
        try:
            # First set session locally
            self.api.set_session(userid=user_id, password='', usertoken=token)
            # Then verify it by making a harmless request
            ret = self.api.get_limits()
            if ret and ret.get('stat') == 'Ok':
                logging.info("Login successful")
                return True
            else:
                self.last_api_error = str(ret) if ret else "Empty response"
                logging.error(f"Login failed: {self.last_api_error}")
                return False
        except Exception as e:
            self.last_api_error = str(e)
            logging.error(f"Login exception: {e}")
            return False
        except Exception as e:
            logging.error(f"Login exception: {e}")
            return False
        except Exception as e:
            logging.error(f"Login exception: {e}")
            return False

    def get_index_ltp(self, index_name):
        # NIFTY token = 26000, SENSEX token = 1
        exchange = 'NSE' if index_name.lower() == 'nifty' else 'BSE'
        token = '26000' if index_name.lower() == 'nifty' else '1'
        ret = self.api.get_quotes(exchange=exchange, token=token)
        self.last_debug_info = f"get_index_ltp({exchange}, {token}) response: {ret}"
        if ret and ret.get('stat') == 'Ok':
            return float(ret.get('lp', 0))
        self.last_api_error = str(ret)
        return None




    def get_nearest_expiry_option(self, index_name, opt_type, strike_price):
        strike_int = int(float(strike_price))
        exch = 'NFO' if index_name.lower() == 'nifty' else 'BFO'
        search_txt = f"{'NIFTY' if index_name.lower() == 'nifty' else 'SENSEX'} {strike_int} {opt_type}"

        debug_logs = []
        try:
            underlying_tsym = 'NIFTY' if index_name.lower() == 'nifty' else 'SENSEX'
            underlying_exch = 'NSE' if index_name.lower() == 'nifty' else 'BSE'
            ret = self.api.get_option_chain(exchange=underlying_exch, tradingsymbol=underlying_tsym, strikeprice=strike_price, count=5)
            debug_logs.append(f"get_option_chain response: {ret}")

            if ret and ret.get('stat') == 'Ok':
                values = ret.get('values', [])
                options = [v for v in values if v.get('optt') == opt_type.upper()]
                if options:
                    options.sort(key=lambda x: abs(float(x.get('strprc', 0)) - strike_price))
                    self.last_debug_info = " | ".join(debug_logs)
                    return options[0]

            ret_search = self.api.searchscrip(exchange=exch, searchtext=search_txt)
            debug_logs.append(f"searchscrip({exch}, '{search_txt}') response: {ret_search}")

            if ret_search and ret_search.get('stat') == 'Ok':
                values = ret_search.get('values', [])
                if values:
                    self.last_debug_info = " | ".join(debug_logs)
                    return values[0]

            self.last_debug_info = " | ".join(debug_logs)
            self.last_api_error = str(ret_search)
        except Exception as e:
            self.last_debug_info = f"Exception: {str(e)}"
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
