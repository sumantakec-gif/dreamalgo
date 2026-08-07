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
    st.header("Authentication")

    user_id = st.text_input("User ID", value="FZ06795")
    api_key_only = st.text_input("API Key", value="c1754e77127444d4912bdaadce1c3b2e")
    api_secret = st.text_input("API Secret", value="2026.404dd20858d8465a824edf9f733f68867e9b92909ed07cd4", type="password")

    # Flattrade technically expects ClientID:::API_KEY for its app_key parameters
    full_api_key = f"{user_id}:::{api_key_only}"

    st.markdown("---")
    st.markdown("**Method 1: Manual Auth (Browser Redirect)**")
    auth_url = f"https://auth.flattrade.in/?app_key={full_api_key}"
    st.markdown(f"[Click Here to Login to Flattrade]({auth_url})")

    query_params = st.query_params
    url_code = query_params.get("code", "")
    auth_code = st.text_input("Auth Code (Auto-filled)", value=url_code)

    if st.button("Generate Token & Login") or (url_code and not st.session_state.logged_in):
        if not api_key_only or not api_secret or not auth_code:
            st.error("API Key, Secret, and Auth Code are required.")
        else:
            uid, token = st.session_state.api.generate_session_token(full_api_key, api_secret, auth_code)
            if uid and token:
                if st.session_state.api.login(uid, token):
                    st.session_state.logged_in = True
                    st.success(f"Logged in successfully as {uid}!")
                    st.query_params.clear()
                else:
                    st.error(f"Login validation failed! API Error: {st.session_state.api.last_api_error}")
            else:
                st.error(f"Token Generation failed! API Error: {st.session_state.api.last_api_error}")


    st.markdown("---")
    st.markdown("**Method 2: Auto Login (Credentials)**")
    password = st.text_input("Password", value="Sreya@123", type="password")
    totp = st.text_input("TOTP (Code or Secret Key)")

    if st.button("Auto Login"):
        if not user_id or not password or not totp or not api_key_only or not api_secret:
            st.error("All fields including API Key/Secret are required for Auto Login.")
        else:
            if st.session_state.api.login_direct(user_id, password, totp, full_api_key, api_secret):
                st.session_state.logged_in = True
                st.success(f"Auto-Logged in successfully as {user_id}!")
            else:
                st.error(f"Auto Login failed! API Response: {st.session_state.api.last_api_error}")


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
                option = None
                ltp = st.session_state.api.get_index_ltp(index_name)
                if not ltp:
                    st.error(f"Could not fetch live price for {index_name}. Is market open/token correct?")
                    st.session_state.running = False
                else:
                    round_val = 50 if index_name == 'NIFTY' else 100
                    atm_strike = round(ltp / round_val) * round_val

                    if strike_selection == "ATM":
                        selected_strike = atm_strike
                        st.info(f"ATM Selected: {selected_strike} (LTP: {ltp})")
                    else:
                        selected_strike = atm_strike + otm_range if opt_type == 'CE' else atm_strike - otm_range
                        st.info(f"OTM Selected: {selected_strike} (LTP: {ltp})")


                    st.info(f"Searching option: {index_name}, {opt_type}, strike={selected_strike}")
                    option = st.session_state.api.get_nearest_expiry_option(index_name, opt_type, selected_strike)
                    if not option:
                        st.error(f"Search failed. Last API Debug: {st.session_state.api.last_debug_info}")


                if option:
                    st.success(f"Selected Script: {option['tsym']}")
                    st.session_state.strategy = StrategyController(
                        st.session_state.api, option['tsym'], option['token'], option['exch'],
                        mode, is_paper, qty, investment, target_pts, sl_pts
                    )
                else:
                    st.error("Could not find matching option script.")
                    st.session_state.running = False



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

# Main Area
st.title("Flattrade Options Algo Trading")

# We will handle the loop here instead of using st.rerun() globally if running
if st.session_state.running and st.session_state.strategy:
    # Get initial data
    df = st.session_state.strategy.fetch_and_calculate()

    col1, col2 = st.columns([3, 1])

    with col1:
        chart_placeholder = st.empty()
    with col2:
        ltp_placeholder = st.empty()
        pnl_placeholder = st.empty()

    logs_placeholder = st.empty()
    reports_placeholder = st.empty()

    while st.session_state.running:
        df = st.session_state.strategy.fetch_and_calculate()
        if not df.empty:
            st.session_state.strategy.evaluate_signals(df)

            # Update placeholders
            chart_placeholder.plotly_chart(render_chart(df), use_container_width=True)

            latest_close = df.iloc[-1]['close']
            ltp_placeholder.metric("Last Traded Price", f"₹ {latest_close:.2f}")
            pnl_placeholder.metric("Live Running P&L", f"₹ {st.session_state.strategy.running_pnl:.2f}")

        logs = get_trade_logs(20)
        if logs:
            log_data = [{"Time": l.timestamp, "Message": l.message} for l in logs]
            logs_placeholder.dataframe(pd.DataFrame(log_data), use_container_width=True)

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

        time.sleep(5)
else:
    # Just render static placeholders if not running
    chart_placeholder = st.empty()
    pnl_placeholder = st.empty()
    logs_placeholder = st.empty()
    reports_placeholder = st.empty()

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
