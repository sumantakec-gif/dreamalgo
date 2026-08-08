import pandas as pd
import ta
import time
from datetime import datetime
from src.database.crud import insert_candlestick, insert_trade_log, insert_order_report

class StrategyController:
    def __init__(self, api_client, symbol, token, exchange, mode, is_paper, qty, investment_amount, target_pts, sl_pts, interval=1):
        self.interval = interval
        self.api = api_client
        self.symbol = symbol
        self.token = token
        self.exchange = exchange
        self.mode = mode # 'BUY' or 'SELL'
        self.is_paper = is_paper
        self.qty = qty
        self.investment_amount = investment_amount
        self.target_pts = target_pts
        self.sl_pts = sl_pts

        self.position = 0
        self.entry_price = 0.0
        self.running_pnl = 0.0

    def calculate_indicators(self, df: pd.DataFrame):
        if len(df) < 1:
            return df

        if len(df) >= 9: df['ema_9'] = ta.trend.EMAIndicator(close=df['close'], window=9).ema_indicator()
        if len(df) >= 25: df['ema_25'] = ta.trend.EMAIndicator(close=df['close'], window=25).ema_indicator()
        if len(df) >= 50: df['ema_50_low'] = ta.trend.EMAIndicator(close=df['low'], window=50).ema_indicator()
        if len(df) >= 250: df['ema_250'] = ta.trend.EMAIndicator(close=df['close'], window=250).ema_indicator()
        df['vwap'] = ta.volume.VolumeWeightedAveragePrice(
            high=df['high'], low=df['low'], close=df['close'], volume=df['volume']
        ).volume_weighted_average_price()

        return df

    def fetch_and_calculate(self):
        # Fetch data since today's start
        today = datetime.now()
        from datetime import timedelta
        start_secs = str(int((today - timedelta(days=5)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))

        data = self.api.get_intraday_data(self.exchange, self.token, start_secs, self.interval)
        if not data:
            return pd.DataFrame()

        # Parse data
        records = []
        for d in data:
            try:
                # time format: DD-MM-YYYY HH:MM:SS
                dt = datetime.strptime(d['time'], '%d-%m-%Y %H:%M:%S')
                records.append({
                    'timestamp': dt,
                    'open': float(d['into']),
                    'high': float(d['inth']),
                    'low': float(d['intl']),
                    'close': float(d['intc']),
                    'volume': int(d['v']),
                    'vwap': float(d['intvwap'])
                })
            except Exception as e:
                import logging
                logging.error(f"Error parsing intraday data record: {e}, {d}")
                continue

        df = pd.DataFrame(records)
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Save to DB (only latest few to avoid overhead, or all if needed)
        for _, row in df.tail(1).iterrows():
            try:
                insert_candlestick(
                    self.symbol, self.token, row['timestamp'],
                    row['open'], row['high'], row['low'], row['close'],
                    row['volume'], row['vwap']
                )
            except Exception:
                pass

        return self.calculate_indicators(df)

    def evaluate_signals(self, df):
        if len(df) < 3 or 'ema_9' not in df.columns:
            return

        # Use the last fully closed candle for evaluation
        closed_candle = df.iloc[-2]
        prev_candle = df.iloc[-3]

        close_price = closed_candle['close']
        ema_9 = closed_candle['ema_9']

        prev_close = prev_candle['close']
        prev_ema_9 = prev_candle['ema_9']

        if pd.isna(ema_9) or pd.isna(prev_ema_9):
            return

        if self.position == 0:
            # We want an actual crossover to prevent rapid re-entries
            buy_signal = (prev_close <= prev_ema_9) and (close_price > ema_9)
            sell_signal = (prev_close >= prev_ema_9) and (close_price < ema_9)

            if self.mode == 'BUY' and buy_signal:
                self.execute_trade('BUY', float(close_price))
            elif self.mode == 'SELL' and sell_signal:
                self.execute_trade('SELL', float(close_price))
        else:
            # Check Stoploss or Target based on EMA
            if self.mode == 'BUY' and close_price < ema_9:
                self.execute_trade('SELL', float(close_price), reason="EMA SL")
            elif self.mode == 'SELL' and close_price > ema_9:
                self.execute_trade('BUY', float(close_price), reason="EMA SL")
            else:
                # Check fixed points Target/SL using the current live price (we can use live price for target/sl)
                live_price = df.iloc[-1]['close']
                pnl_pts = (live_price - self.entry_price) if self.mode == 'BUY' else (self.entry_price - live_price)
                if self.target_pts > 0 and pnl_pts >= self.target_pts:
                    self.execute_trade('SELL' if self.mode == 'BUY' else 'BUY', float(live_price), reason="TARGET")
                elif self.sl_pts > 0 and pnl_pts <= -self.sl_pts:
                    self.execute_trade('SELL' if self.mode == 'BUY' else 'BUY', float(live_price), reason="SL")

    def execute_trade(self, action, price, reason="ENTRY"):
        resp = self.api.place_order(action[0], self.exchange, self.symbol, self.qty, price, is_paper=self.is_paper)
        if resp and resp.get('stat') == 'Ok':
            msg = f"{action} {self.symbol} @ {price} ({reason})"
            insert_trade_log(
                timestamp=datetime.now(),
                symbol=self.symbol,
                token=self.token,
                trade_type=action,
                price=price,
                quantity=self.qty,
                message=msg,
                is_paper_trade=self.is_paper
            )

            if self.position == 0:
                self.position = self.qty if action == 'BUY' else -self.qty
                self.entry_price = price
            else:
                pnl = (price - self.entry_price) * self.qty if self.position > 0 else (self.entry_price - price) * self.qty
                self.running_pnl += pnl
                self.position = 0
                insert_order_report(
                    timestamp=datetime.now(),
                    symbol=self.symbol,
                    exp_date='N/A', # Add logic to extract
                    strike_price=0.0,
                    op_type='N/A',
                    buy_sell=action,
                    qty=self.qty,
                    price=price,
                    trade_qty=self.qty,
                    avg_price=price,
                    points=float(price - self.entry_price) if action=='SELL' else float(self.entry_price - price),
                    amount=float(pnl),
                    running_pnl=float(self.running_pnl),
                    gain_percent=float((pnl / self.investment_amount) * 100) if self.investment_amount > 0 else 0,
                    invested_amount=self.investment_amount
                )
