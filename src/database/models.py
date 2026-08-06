from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv('DB_NAME', 'flattrade_db')
DB_USER = os.getenv('DB_USER', 'jules')
DB_PASS = os.getenv('DB_PASS', 'jules')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

engine = create_engine(f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
Base = declarative_base()

class Candlestick(Base):
    __tablename__ = 'candlesticks'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    token = Column(String)
    timestamp = Column(DateTime)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    vwap = Column(Float)

class TradeLog(Base):
    __tablename__ = 'trade_logs'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    symbol = Column(String)
    token = Column(String)
    trade_type = Column(String)  # BUY or SELL
    price = Column(Float)
    quantity = Column(Integer)
    message = Column(String)
    is_paper_trade = Column(Boolean)

class OrderReport(Base):
    __tablename__ = 'order_reports'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    symbol = Column(String)
    exp_date = Column(String)
    strike_price = Column(Float)
    op_type = Column(String)
    buy_sell = Column(String)
    qty = Column(Integer)
    price = Column(Float)
    trade_qty = Column(Integer)
    avg_price = Column(Float)
    points = Column(Float)
    amount = Column(Float)
    running_pnl = Column(Float)
    gain_percent = Column(Float)
    invested_amount = Column(Float)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()
