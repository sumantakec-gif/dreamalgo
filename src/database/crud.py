from datetime import datetime
from src.database.models import get_session, Candlestick, TradeLog, OrderReport, UserConfig

def insert_candlestick(symbol: str, token: str, timestamp: datetime, open_price: float, high: float, low: float, close: float, volume: int, vwap: float):
    session = get_session()
    try:
        # Check if already exists to avoid duplicates
        existing = session.query(Candlestick).filter_by(token=token, timestamp=timestamp).first()
        if existing:
            # Update existing
            existing.open_price = open_price
            existing.high = high
            existing.low = low
            existing.close = close
            existing.volume = volume
            existing.vwap = vwap
            session.commit()
            return

        candle = Candlestick(
            symbol=symbol,
            token=token,
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            vwap=vwap
        )
        session.add(candle)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def insert_trade_log(timestamp: datetime, symbol: str, token: str, trade_type: str, price: float, quantity: int, message: str, is_paper_trade: bool):
    session = get_session()
    try:
        log = TradeLog(
            timestamp=timestamp,
            symbol=symbol,
            token=token,
            trade_type=trade_type,
            price=price,
            quantity=quantity,
            message=message,
            is_paper_trade=is_paper_trade
        )
        session.add(log)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def insert_order_report(timestamp: datetime, symbol: str, exp_date: str, strike_price: float, op_type: str, buy_sell: str, qty: int, price: float, trade_qty: int, avg_price: float, points: float, amount: float, running_pnl: float, gain_percent: float, invested_amount: float):
    session = get_session()
    try:
        report = OrderReport(
            timestamp=timestamp,
            symbol=symbol,
            exp_date=exp_date,
            strike_price=strike_price,
            op_type=op_type,
            buy_sell=buy_sell,
            qty=qty,
            price=price,
            trade_qty=trade_qty,
            avg_price=avg_price,
            points=points,
            amount=amount,
            running_pnl=running_pnl,
            gain_percent=gain_percent,
            invested_amount=invested_amount
        )
        session.add(report)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_trade_logs(limit=100):
    session = get_session()
    try:
        return session.query(TradeLog).order_by(TradeLog.timestamp.desc()).limit(limit).all()
    finally:
        session.close()

def get_today_pnl():
    session = get_session()
    try:
        from datetime import date
        today = date.today()
        # Get latest order reports for today
        reports = session.query(OrderReport).filter(
            OrderReport.timestamp >= datetime.combine(today, datetime.min.time()),
            OrderReport.timestamp <= datetime.combine(today, datetime.max.time())
        ).all()
        # Or if order report isn't used much, check TradeLog?
        # Actually OrderReport has `amount` which is PnL (for SELL to close)
        # However, the strategy class updates `running_pnl` inside the loop.
        # But we need net profit/loss across all trades today.

        # Let's sum the running PnL from closed positions for today.
        # Actually, OrderReport stores `amount` which is the P&L of that specific trade.
        # Let's sum the 'amount' field for all OrderReport entries for today where it represents a realized P&L.

        total_pnl = sum([r.amount for r in reports if r.amount is not None])
        return total_pnl
    except Exception as e:
        print(f"Error calculating PnL: {e}")
        return 0.0
    finally:
        session.close()


def get_order_reports():
    session = get_session()
    try:
        return session.query(OrderReport).order_by(OrderReport.timestamp.desc()).all()
    finally:
        session.close()

def save_user_config(broker, user_id, api_key, api_secret, password="", totp=""):
    session = get_session()
    try:
        config = session.query(UserConfig).filter_by(broker=broker).first()
        if not config:
            config = UserConfig(broker=broker)
            session.add(config)
        config.user_id = user_id
        config.api_key = api_key
        config.api_secret = api_secret
        config.password = password
        config.totp = totp
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_user_config(broker):
    session = get_session()
    try:
        return session.query(UserConfig).filter_by(broker=broker).first()
    finally:
        session.close()
