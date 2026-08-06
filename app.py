import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
from src.trading.api import FlattradeClient
from src.trading.strategy import StrategyController
from src.database.crud import get_trade_logs, get_order_reports
from io import BytesIO

st.set_page_config(layout="wide", page_title="Flattrade Option Algo")

if 'api' not in st.session_state:
    st.session_state.api = FlattradeClient()
    st.session_state.logged_in = False
    st.session_state.strategy = None
    st.session_state.running = False

# Sidebar
with st.sidebar:
    st.header("Credentials")
    uid = st.text_input("User ID")
    token = st.text_input("API Token", type="password")

    if st.button("Login"):
        if st.session_state.api.login(uid, token):
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
        else:
            st.error("Login failed")


    st.header("Strategy Settings")
    index_name = st.selectbox("Index", ["NIFTY", "SENSEX"])
    opt_type = st.selectbox("Option Type (CE/PE)", ["CE", "PE"])
    strike_selection = st.selectbox("Strike Selection", ["ATM", "OTM Range"])
    otm_range = st.number_input("OTM Range Offset (Points)", value=100) if strike_selection == "OTM Range" else 0
    lot_price_min = st.number_input("Lot Price Min", value=50.0)
    lot_price_max = st.number_input("Lot Price Max", value=200.0)
    mode = st.selectbox("Mode", ["BUY", "SELL"])

    is_paper = st.checkbox("Paper Trade", value=True)
    qty = st.number_input("Lot Size / Quantity", value=50)
    investment = st.number_input("Total Amount to Invest", value=100000)
    target_pts = st.number_input("Target (Points)", value=20)
    sl_pts = st.number_input("Stoploss (Points)", value=10)

    if st.button("Start Algo" if not st.session_state.running else "Stop Algo"):
        if not st.session_state.logged_in:
            st.error("Please login first!")
        else:
            st.session_state.running = not st.session_state.running
            if st.session_state.running:
                # Script Selection

                selected_strike = 0
                ltp = st.session_state.api.get_index_ltp(index_name)
                if ltp:
                    round_val = 50 if index_name == 'NIFTY' else 100
                    atm_strike = round(ltp / round_val) * round_val

                    if strike_selection == "ATM":
                        selected_strike = atm_strike
                        st.info(f"ATM Selected: {selected_strike}")
                    else:
                        selected_strike = atm_strike + otm_range if opt_type == 'CE' else atm_strike - otm_range
                        st.info(f"OTM Selected: {selected_strike}")

                # Fetch option and verify lot price if needed (requires fetching quote for option, simplified here)
                option = st.session_state.api.get_nearest_expiry_option(index_name, opt_type, selected_strike)

                if option:
                    st.success(f"Selected Script: {option['tsym']}")
                    st.session_state.strategy = StrategyController(
                        st.session_state.api, option['tsym'], option['token'], option['exch'],
                        mode, is_paper, qty, investment, target_pts, sl_pts
                    )
                else:
                    st.error("Could not find matching option script.")
                    st.session_state.running = False

# Main Area
st.title("Flattrade Options Algo Trading")

chart_placeholder = st.empty()
pnl_placeholder = st.empty()
logs_placeholder = st.empty()
reports_placeholder = st.empty()

# Function to render chart
def render_chart(df):
    if df.empty:
        return go.Figure()
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'],
                open=df['open'], high=df['high'],
                low=df['low'], close=df['close'], name="Candles")])
    if 'ema_9' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_9'], mode='lines', name='9 EMA Close'))
    if 'ema_25' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_25'], mode='lines', name='25 EMA Close'))
    if 'ema_50_low' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_50_low'], mode='lines', name='50 EMA Low'))
    if 'ema_250' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_250'], mode='lines', name='250 EMA Close'))
    if 'vwap' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['vwap'], mode='lines', name='VWAP'))
    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    return fig

# Main Loop Execution for Streamlit
if st.session_state.running and st.session_state.strategy:
    df = st.session_state.strategy.fetch_and_calculate()
    if not df.empty:
        st.session_state.strategy.evaluate_signals(df)
        chart_placeholder.plotly_chart(render_chart(df), use_container_width=True)

    pnl_placeholder.metric("Live Running P&L", f"₹ {st.session_state.strategy.running_pnl:.2f}")

    # Auto refresh every 5 seconds (using st.rerun())
    time.sleep(5)
    st.rerun()

# Logs and Reports (rendered regardless of running state)
st.subheader("Trade Logs")
logs = get_trade_logs(20)
if logs:
    log_data = [{"Time": l.timestamp, "Message": l.message} for l in logs]
    logs_placeholder.dataframe(pd.DataFrame(log_data), use_container_width=True)

st.subheader("Order Reports")
reports = get_order_reports()
if reports:
    rep_df = pd.DataFrame([{
        "Symbol": r.symbol, "ExpDate": r.exp_date, "StrikePrice": r.strike_price, "OpType": r.op_type,
        "BuySell": r.buy_sell, "Qty": r.qty, "Price": r.price, "TradeQty": r.trade_qty,
        "AvgPrice": r.avg_price, "TimeStamp": r.timestamp, "Points": r.points,
        "Amount": r.amount, "Running P&L": r.running_pnl, "Gain %": r.gain_percent,
        "Invested Amount": r.invested_amount
    } for r in reports])
    reports_placeholder.dataframe(rep_df, use_container_width=True)

    # Download Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        rep_df.to_excel(writer, index=False, sheet_name='Orders')
    st.download_button(
        label="Download Orders Excel",
        data=output.getvalue(),
        file_name="order_reports.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
