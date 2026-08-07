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
    def __init__(self, log_callback=None):
        self.api = NorenApiPy()
        self.log = log_callback if log_callback else lambda x: None
        self.last_debug_info = ""
        self.last_api_error = ""








    def login_direct(self, user_id, password, totp, api_key_full, api_secret):
        import pyotp
        import requests
        import hashlib
        import json

        try:
            self.log("Starting Direct Auth Flow...")
            if len(totp) > 10 and not totp.isdigit():
                totp_code = pyotp.TOTP(totp).now()
                self.log(f"PyOTP Generated TOTP: {totp_code}")
            else:
                totp_code = totp
                self.log(f"Using manual TOTP: {totp_code}")

            pwd = hashlib.sha256(password.encode('utf-8')).hexdigest()
            u_app_key = f'{user_id}|{api_secret}'
            app_key = hashlib.sha256(u_app_key.encode('utf-8')).hexdigest()

            # Since Flattrade SDK eats error messages, let's manually hit QuickAuth
            values = {
                "source": "API",
                "apkversion": "1.0.0",
                "uid": user_id,
                "pwd": pwd,
                "factor2": totp_code,
                "vc": f"{user_id}_U",
                "appkey": app_key,
                "imei": "abc123xyz"
            }

            payload = 'jData=' + json.dumps(values)
            url = "https://piconnect.flattrade.in/PiConnectAPI/QuickAuth"

            self.log("Sending POST to QuickAuth")
            res = requests.post(url, data=payload)

            self.log(f"HTTP Status: {res.status_code} | Raw Response: {res.text}")

            try:
                data = res.json()
            except Exception:
                data = {}

            if data.get('stat') == 'Ok':
                self.log("Validating local session...")
                return self.login(user_id, data.get('susertoken'))
            else:
                self.last_api_error = data.get('emsg', str(data))
                return False

        except Exception as e:
            self.last_api_error = str(e)
            self.log(f"Exception occurred: {str(e)}")
            return False

        except Exception as e:
            self.last_api_error = str(e)
            return False
        except Exception as e:
            self.last_api_error = str(e)
            return False

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

            self.log(f"Sending token generation request for API Key: {api_key}")
            response = requests.post("https://authapi.flattrade.in/trade/apitoken", json=payload)
            self.log(f"Token Gen HTTP {response.status_code} | Response: {response.text}")
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
            self.api.set_session(userid=user_id, password='', usertoken=token)
            self.log(f"Testing token validity via get_limits()...")
            ret = self.api.get_limits()
            if ret and ret.get('stat') == 'Ok':
                logging.info("Login successful")

                # Automatically save the valid session token
                import json, os
                with open('.flattrade_session.json', 'w') as f:
                    json.dump({'uid': user_id, 'token': token}, f)

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
        self.log(f"Fetching LTP for {index_name} (token={token})")
        ret = self.api.get_quotes(exchange=exchange, token=token)
        self.log(f"LTP Response: {ret}")
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
            self.log(f"Calling get_option_chain({underlying_exch}, {underlying_tsym}, {strike_price})")
            ret = self.api.get_option_chain(exchange=underlying_exch, tradingsymbol=underlying_tsym, strikeprice=strike_price, count=5)
            self.log(f"get_option_chain response: {ret}")

            if ret and ret.get('stat') == 'Ok':
                values = ret.get('values', [])
                options = [v for v in values if v.get('optt') == opt_type.upper()]
                if options:
                    options.sort(key=lambda x: abs(float(x.get('strprc', 0)) - strike_price))

                    return options[0]

            self.log(f"Calling searchscrip({exch}, '{search_txt}')")
            ret_search = self.api.searchscrip(exchange=exch, searchtext=search_txt)
            self.log(f"searchscrip response: {ret_search}")

            if ret_search and ret_search.get('stat') == 'Ok':
                values = ret_search.get('values', [])
                if values:

                    return values[0]


            self.last_api_error = str(ret_search)
        except Exception as e:
            self.last_debug_info = f"Exception: {str(e)}"
            logging.error(f"Error fetching option chain: {e}")
        return None

    def get_intraday_data(self, exchange, token, start_time):
        try:
            self.log(f"Fetching intraday data for token={token}, start={start_time}")
            ret = self.api.get_time_price_series(exchange=exchange, token=token, starttime=str(start_time))
            self.log(f"get_time_price_series returned: {ret}")
            if isinstance(ret, list) and len(ret) > 0 and ret[0].get('stat') == 'Ok':
                return ret
            elif isinstance(ret, list) and len(ret) > 0 and 'stat' not in ret[0]:
                return ret
            elif isinstance(ret, dict) and ret.get('stat') == 'Ok':
                return [ret] # some NorenAPI versions return dict?

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
            self.log(f"Placing Order: {buy_or_sell} {quantity} {symbol} @ {price} | Type: {order_type}")
            ret = self.api.placeOrder(order)
            self.log(f"Order Response: {ret}")
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
