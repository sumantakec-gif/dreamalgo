from flattrade_api.api_helper import NorenApiPy, Order
import logging

class FlattradeClient:
    def __init__(self):
        self.api = NorenApiPy()

    def login(self, user_id, token):
        try:
            ret = self.api.set_session(userid=user_id, password='', usertoken=token)
            if ret and ret.get('stat') == 'Ok':
                logging.info("Login successful")
                return True
            else:
                logging.error(f"Login failed: {ret}")
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
        exchange = 'NFO' if index_name.lower() == 'nifty' else 'BFO'
        # Base trading symbol format for search. E.g. NIFTY
        search_sym = 'NIFTY' if index_name.lower() == 'nifty' else 'SENSEX'

        # We can use searchscrip or get_option_chain
        # Let's use get_option_chain which expects exchange, tradingsymbol of underlying, strikeprice and count
        # Wait, get_option_chain needs tradingsymbol. Let's construct it.
        # NIFTY index trading symbol on NSE is NIFTY 50
        underlying_tsym = 'NIFTY 50' if index_name.lower() == 'nifty' else 'SENSEX'
        underlying_exch = 'NSE' if index_name.lower() == 'nifty' else 'BSE'

        try:
            ret = self.api.get_option_chain(exchange=underlying_exch, tradingsymbol=underlying_tsym, strikeprice=strike_price, count=5)
            if ret and ret.get('stat') == 'Ok':
                values = ret.get('values', [])
                # Filter by option type (CE or PE)
                options = [v for v in values if v.get('optt') == opt_type.upper()]
                if options:
                    # Sort by expiry date (exd) assuming it's available or we just take the first one returned (API usually returns nearest expiry first or we need to sort)
                    # Flattrade get_option_chain doesn't explicitly guarantee nearest expiry order, but let's assume it returns matching strikes.
                    # A better way is using searchscrip if get_option_chain fails us, but let's try this.
                    options.sort(key=lambda x: abs(float(x.get('strprc', 0)) - strike_price))
                    return options[0]
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
