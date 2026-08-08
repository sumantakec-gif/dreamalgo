import streamlit as st
import pandas as pd
import time
from src.trading.api import FlattradeClient
from src.trading.strategy import StrategyController
from src.database.crud import get_trade_logs, get_order_reports, save_user_config, get_user_config
from io import BytesIO


import os
import json

st.set_page_config(layout="wide", page_title="Flattrade Option Algo")

def save_session_cache(uid, token):
    with open('.flattrade_session.json', 'w') as f:
        json.dump({'uid': uid, 'token': token}, f)

def load_session_cache():
    if os.path.exists('.flattrade_session.json'):
        try:
            with open('.flattrade_session.json', 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def add_sys_log(msg):
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.system_logs.append(f"[{timestamp}] {msg}")
    if len(st.session_state.system_logs) > 50:
        st.session_state.system_logs.pop(0)

if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False

if 'api' not in st.session_state or getattr(st.session_state.api, 'log', None) is None:
    st.session_state.api = FlattradeClient(log_callback=add_sys_log)

if 'system_logs' not in st.session_state:
    st.session_state.system_logs = []
if 'strategy' not in st.session_state:
    st.session_state.strategy = None
if 'running' not in st.session_state:
    st.session_state.running = False

# Attempt to auto-login from cached file if not already logged in
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    cached = load_session_cache()
    if cached:
        if st.session_state.api.login(cached['uid'], cached['token']):
            st.session_state.logged_in = True
            add_sys_log(f"Restored session from cache for {cached['uid']}")







# Sidebar
with st.sidebar:
    st.header("Broker Connection")
    broker = st.selectbox("Select Broker", ["Flattrade"])

    config = get_user_config(broker)

    if not st.session_state.logged_in:
        if not config:
            st.warning("Please configure your credentials in the ⚙️ Settings menu first.")
        else:
            st.markdown("---")

            auth_url = f"https://auth.flattrade.in/?app_key={config.api_key}"
            st.markdown(f'<a href="{auth_url}" target="_self"><button style="background-color:#4CAF50; color:white; padding:10px 20px; text-align:center; border:none; border-radius:4px; cursor:pointer; width:100%;">Connect Broker</button></a>', unsafe_allow_html=True)

            query_params = st.query_params
            url_code = query_params.get("code", "")

            if url_code:
                uid, token = st.session_state.api.generate_session_token(config.api_key, config.api_secret, url_code)
                if uid and token:
                    if st.session_state.api.login(uid, token):
                        st.session_state.logged_in = True
                        save_session_cache(uid, token)
                        st.success(f"Connected successfully as {uid}!")
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error(f"Login validation failed! API Error: {st.session_state.api.last_api_error}")
                else:
                    st.error(f"Token Generation failed! API Error: {st.session_state.api.last_api_error}")
                    st.query_params.clear()

    else:
        st.success("Broker Connected ✅")
        if st.button("Disconnect Broker"):
            import os
            if os.path.exists(".flattrade_session.json"):
                os.remove(".flattrade_session.json")
            st.session_state.api = None
            st.session_state.logged_in = False
            st.session_state.running = False
            st.session_state.strategy = None
            st.query_params.clear()
            st.rerun()

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
                    st.session_state.system_logs = []
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
                    option = st.session_state.api.get_nearest_expiry_option(index_name, opt_type, selected_strike, lot_price_min, lot_price_max)
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
                    st.session_state.system_logs = []



import plotly.graph_objects as go

def render_chart(df):
    if df.empty:
        return go.Figure()

    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'],
                open=df['open'], high=df['high'],
                low=df['low'], close=df['close'], name="Candles",
                increasing_line_color='#26a69a', decreasing_line_color='#ef5350')])

    if 'ema_9' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_9'], mode='lines', line=dict(color='magenta', width=1.5), name='9 EMA Close'))
    if 'ema_25' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_25'], mode='lines', line=dict(color='green', width=1.5), name='25 EMA Close'))
    if 'ema_50_low' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_50_low'], mode='lines', line=dict(color='blue', width=1.5), name='50 EMA Low'))
    if 'ema_250' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_250'], mode='lines', line=dict(color='orange', width=2), name='250 EMA Close'))
    if 'vwap' in df:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['vwap'], mode='lines', line=dict(color='darkred', width=1.5), name='VWAP'))

    # Hide outside market hours and weekends
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["15:30", "09:15"]),
            dict(bounds=["sat", "mon"])
        ],
        gridcolor='lightgray',
        showgrid=True
    )

    fig.update_yaxes(gridcolor='lightgray', showgrid=True)

    # Add vertical lines for new days
    df['date'] = df['timestamp'].dt.date
    new_days = df[df['date'] != df['date'].shift(1)]['timestamp']
    for nd in new_days:
        fig.add_vline(x=nd, line_dash="dash", line_color="blue", opacity=0.5, line_width=1)

    # Add markers for crossovers (where position would trigger)
    # We can detect historical crossovers for the chart
    if 'ema_9' in df:
        # Cross above
        cross_up = df[(df['close'] > df['ema_9']) & (df['close'].shift(1) <= df['ema_9'].shift(1))]
        if not cross_up.empty:
            fig.add_trace(go.Scatter(x=cross_up['timestamp'], y=cross_up['close'], mode='markers', marker=dict(symbol='cross', size=12, color='black', line=dict(width=2, color='black')), name='Cross Up'))

        # Cross below
        cross_down = df[(df['close'] < df['ema_9']) & (df['close'].shift(1) >= df['ema_9'].shift(1))]
        if not cross_down.empty:
            fig.add_trace(go.Scatter(x=cross_down['timestamp'], y=cross_down['close'], mode='markers', marker=dict(symbol='cross', size=12, color='black', line=dict(width=2, color='black')), name='Cross Down'))

    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        uirevision='constant',
        margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    return fig


st.subheader("System Logs (Live API Debug)")
if st.session_state.system_logs:
    log_text = "\n".join(st.session_state.system_logs[::-1])
    st.markdown(f'<div style="height: 200px; overflow-y: scroll; background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 12px; white-space: pre-wrap;">{log_text}</div>', unsafe_allow_html=True)


# Main Area

# Top right Settings Button
col_main, col_settings = st.columns([9, 1])
with col_settings:
    if st.button("⚙️ Settings"):
        st.session_state.show_settings = not st.session_state.show_settings

if st.session_state.show_settings:
    st.markdown("### User Configuration")
    config = get_user_config("Flattrade")
    with st.form("settings_form"):
        s_user_id = st.text_input("User ID", value=config.user_id if config else "")
        s_api_key = st.text_input("API Key", value=config.api_key if config else "")
        s_api_secret = st.text_input("API Secret", value=config.api_secret if config else "", type="password")

        if st.form_submit_button("Save Credentials"):
            save_user_config("Flattrade", s_user_id, s_api_key, s_api_secret)
            st.success("Credentials saved to database successfully!")
            st.session_state.show_settings = False

st.title("Flattrade Options Algo Trading")


@st.fragment(run_every=5)
def run_trading_loop():
    if st.session_state.running and st.session_state.strategy:
        df = st.session_state.strategy.fetch_and_calculate()

        col1, col2 = st.columns([3, 1])

        with col1:
            if not df.empty:
                st.session_state.strategy.evaluate_signals(df)
                st.plotly_chart(render_chart(df), use_container_width=True, key="live_chart", config={"scrollZoom": True})
            else:
                st.warning("Waiting for candlestick data... (API might have returned empty data)")

        with col2:
            if not df.empty:
                latest_close = df.iloc[-1]['close']
                st.metric("Last Traded Price", f"₹ {latest_close:.2f}")
                st.metric("Live Running P&L", f"₹ {st.session_state.strategy.running_pnl:.2f}")
            else:
                st.metric("Last Traded Price", "---")
                st.metric("Live Running P&L", "---")

        logs = get_trade_logs(20)
        if logs:
            log_data = [{"Time": l.timestamp, "Message": l.message} for l in logs]
            st.dataframe(pd.DataFrame(log_data), use_container_width=True)

        reports = get_order_reports()
        if reports:
            rep_df = pd.DataFrame([{
                "Symbol": r.symbol, "ExpDate": r.exp_date, "StrikePrice": r.strike_price, "OpType": r.op_type,
                "BuySell": r.buy_sell, "Qty": r.qty, "Price": r.price, "TradeQty": r.trade_qty,
                "AvgPrice": r.avg_price, "TimeStamp": r.timestamp, "Points": r.points,
                "Amount": r.amount, "Running P&L": r.running_pnl, "Gain %": r.gain_percent,
                "Invested Amount": r.invested_amount
            } for r in reports])
            st.dataframe(rep_df, use_container_width=True)
    else:
        st.info("System is ready. Start the bot from the sidebar to begin trading.")

        st.subheader("Trade Logs")
        logs = get_trade_logs(20)
        if logs:
            log_data = [{"Time": l.timestamp, "Message": l.message} for l in logs]
            st.dataframe(pd.DataFrame(log_data), use_container_width=True)

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
            st.dataframe(rep_df, use_container_width=True)

run_trading_loop()
