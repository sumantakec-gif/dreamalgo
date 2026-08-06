from datetime import datetime
from src.database.models import get_session, Candlestick, TradeLog, OrderReport

def insert_candlestick(symbol: str, token: str, timestamp: datetime, open_price: float, high: float, low: float, close: float, volume: int, vwap: float):
    session = get_session()
    try:
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

def get_order_reports():
    session = get_session()
    try:
        return session.query(OrderReport).order_by(OrderReport.timestamp.desc()).all()
    finally:
        session.close()
