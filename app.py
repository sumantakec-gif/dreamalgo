import streamlit as st

# Force IPv4 for all outbound connections
import socket
old_getaddrinfo = socket.getaddrinfo

def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]

socket.getaddrinfo = new_getaddrinfo


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
if 'show_ema_9' not in st.session_state: st.session_state.show_ema_9 = True
if 'show_ema_25' not in st.session_state: st.session_state.show_ema_25 = True
if 'show_ema_50' not in st.session_state: st.session_state.show_ema_50 = True
if 'show_ema_250' not in st.session_state: st.session_state.show_ema_250 = True
if 'show_vwap' not in st.session_state: st.session_state.show_vwap = True

# Attempt to auto-login from cached file if not already logged in
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    cached = load_session_cache()
    if cached:
        if st.session_state.api.login(cached['uid'], cached['token']):
            st.session_state.logged_in = True
            add_sys_log(f"Restored session from cache for {cached['uid']}")







st.title("DreamAlgo")

# Chart Controls (Decoupled from Algo Running state)
col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)
with col_c1:
    index_name = st.selectbox("Index", ["NIFTY", "SENSEX"])

# Fetch LTP early to populate dynamic strike dropdown
ltp = None
if st.session_state.logged_in:
    ltp = st.session_state.api.get_index_ltp(index_name)

with col_c2:
    opt_type = st.selectbox("Option Type (CE/PE)", ["CE", "PE"])

with col_c3:
    expiry_selection = st.selectbox("Expiry", ["Current Expiry", "Next Expiry"])

with col_c4:
    if ltp:
        round_val = 50 if index_name == 'NIFTY' else 100
        atm_strike = round(ltp / round_val) * round_val
        spot_options = []
        for i in range(-20, 21):
            if i == 0:
                spot_options.append(f"{atm_strike} (ATM)")
            elif i > 0:
                spot_options.append(f"{atm_strike + (i * round_val)} (ATM +{i})")
            else:
                spot_options.append(f"{atm_strike + (i * round_val)} (ATM {i})")
        # Set default to ATM
        default_index = spot_options.index(f"{atm_strike} (ATM)")
        strike_selection = st.selectbox("Strike Selection", spot_options, index=default_index)
    else:
        # Fallback if not logged in
        spot_options = ["ATM"]
        for i in range(1, 21):
            spot_options.append(f"ATM +{i}")
            spot_options.append(f"ATM -{i}")
        strike_selection = st.selectbox("Strike Selection", spot_options)

with col_c5:
    chart_interval = st.selectbox("Chart Timeframe", ["1 Min", "3 Min", "5 Min"])
    interval_map = {"1 Min": 1, "3 Min": 3, "5 Min": 5}
    interval_val = interval_map[chart_interval]

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

    lot_price_min = st.number_input("Lot Price Min", value=50.0)
    lot_price_max = st.number_input("Lot Price Max", value=200.0)
    mode = st.selectbox("Mode", ["BUY", "SELL"])

    is_paper = st.checkbox("Paper Trade", value=True)
    qty = st.number_input("Lot Size / Quantity", value=50)
    investment = st.number_input("Total Amount to Invest", value=100000)
    target_pts = st.number_input("Target (Points)", value=20)
    sl_pts = st.number_input("Stoploss (Points)", value=10)

    # Generate the option config dynamically
    selected_option = None
    if st.session_state.logged_in and ltp:
        if " (ATM" in strike_selection:
            # Extract just the strike price integer part
            selected_strike = int(strike_selection.split(" ")[0])
        else:
            round_val = 50 if index_name == 'NIFTY' else 100
            atm_strike = round(ltp / round_val) * round_val
            if strike_selection == "ATM":
                selected_strike = atm_strike
            else:
                offset_str = strike_selection.split(" ")[1]
                offset = int(offset_str)
                selected_strike = atm_strike + (offset * round_val) if opt_type == 'CE' else atm_strike - (offset * round_val)

        is_next_expiry = expiry_selection == "Next Expiry"
        selected_option = st.session_state.api.get_nearest_expiry_option(index_name, opt_type, selected_strike, lot_price_min, lot_price_max, is_next_expiry)

    if st.button("Start Algo" if not st.session_state.running else "Stop Algo"):
        if not st.session_state.logged_in:
            st.error("Please login first!")
        elif not selected_option:
            st.error("Cannot start algo without a valid option script selected!")
        else:
            st.session_state.running = not st.session_state.running
            if st.session_state.running:
                st.session_state.strategy = StrategyController(
                    st.session_state.api, selected_option['tsym'], selected_option['token'], selected_option['exch'],
                    mode, is_paper, qty, investment, target_pts, sl_pts, interval_val
                )
            else:
                st.session_state.strategy = None



from streamlit_lightweight_charts import renderLightweightCharts
import json

def render_chart(df, script_name='Options Algo Chart', timeframe='1 Min'):
    if df.empty:
        return None

    # Format data for Lightweight Charts
    # Time must be string in YYYY-MM-DD format (or UNIX timestamp)
    chart_data = []

    # Keep only columns we need and drop NaNs for the chart
    plot_df = df[['timestamp', 'open', 'high', 'low', 'close']].copy()
    if 'ema_9' in df: plot_df['ema_9'] = df['ema_9']
    if 'ema_25' in df: plot_df['ema_25'] = df['ema_25']
    if 'ema_50_low' in df: plot_df['ema_50_low'] = df['ema_50_low']
    if 'ema_250' in df: plot_df['ema_250'] = df['ema_250']
    if 'vwap' in df: plot_df['vwap'] = df['vwap']

    # We use UNIX timestamps so exact minute is preserved correctly
    plot_df['time'] = plot_df['timestamp'].astype('int64') // 10**9

    candles = plot_df[['time', 'open', 'high', 'low', 'close']].to_dict('records')

    chartOptions = {
        "layout": {
            "textColor": 'black',
            "background": {
                "type": 'solid',
                "color": 'white'
            }
        },
        "watermark": {
            "color": 'rgba(0, 0, 0, 0.1)',
            "visible": True,
            "text": script_name,
            "fontSize": 48,
            "horzAlign": 'center',
            "vertAlign": 'center',
        },
        "timeScale": {
            "timeVisible": True,
            "secondsVisible": False,
        },
        "crosshair": {
            "mode": 1 # Normal mode
        }
    }

    seriesCandlestickChart = [{
        "type": 'Candlestick',
        "data": candles,
        "options": {
            "upColor": '#26a69a',
            "downColor": '#ef5350',
            "borderVisible": False,
            "wickUpColor": '#26a69a',
            "wickDownColor": '#ef5350'
        }
    }]

    # Add indicators if they exist and are enabled
    if 'ema_9' in plot_df and st.session_state.show_ema_9:
        ema9_data = plot_df[['time', 'ema_9']].rename(columns={'ema_9': 'value'}).dropna().to_dict('records')
        seriesCandlestickChart.append({
            "type": 'Line',
            "data": ema9_data,
            "options": {"color": 'magenta', "lineWidth": 1.5, "title": "9 EMA"}
        })

    if 'ema_25' in plot_df and st.session_state.show_ema_25:
        ema25_data = plot_df[['time', 'ema_25']].rename(columns={'ema_25': 'value'}).dropna().to_dict('records')
        seriesCandlestickChart.append({
            "type": 'Line',
            "data": ema25_data,
            "options": {"color": 'green', "lineWidth": 1.5, "title": "25 EMA"}
        })

    if 'ema_50_low' in plot_df and st.session_state.show_ema_50:
        ema50_data = plot_df[['time', 'ema_50_low']].rename(columns={'ema_50_low': 'value'}).dropna().to_dict('records')
        seriesCandlestickChart.append({
            "type": 'Line',
            "data": ema50_data,
            "options": {"color": 'blue', "lineWidth": 1.5, "title": "50 EMA Low"}
        })

    if 'ema_250' in plot_df and st.session_state.show_ema_250:
        ema250_data = plot_df[['time', 'ema_250']].rename(columns={'ema_250': 'value'}).dropna().to_dict('records')
        seriesCandlestickChart.append({
            "type": 'Line',
            "data": ema250_data,
            "options": {"color": 'orange', "lineWidth": 2, "title": "250 EMA"}
        })

    if 'vwap' in plot_df and st.session_state.show_vwap:
        vwap_data = plot_df[['time', 'vwap']].rename(columns={'vwap': 'value'}).dropna().to_dict('records')
        seriesCandlestickChart.append({
            "type": 'Line',
            "data": vwap_data,
            "options": {"color": 'darkred', "lineWidth": 1.5, "title": "VWAP"}
        })

    # Markers for crossovers
    if 'ema_9' in plot_df:
        markers = []
        # Calculate exactly based on last fully closed candle logic
        # Buy: prev_close <= prev_ema9 AND current_close > current_ema9
        # Sell: prev_close >= prev_ema9 AND current_close < current_ema9

        for i in range(1, len(plot_df)):
            prev_row = plot_df.iloc[i-1]
            curr_row = plot_df.iloc[i]

            if pd.isna(prev_row['ema_9']) or pd.isna(curr_row['ema_9']):
                continue

            is_buy = prev_row['close'] <= prev_row['ema_9'] and curr_row['close'] > curr_row['ema_9']
            is_sell = prev_row['close'] >= prev_row['ema_9'] and curr_row['close'] < curr_row['ema_9']

            if is_buy:
                markers.append({
                    "time": int(curr_row['time']),
                    "position": "belowBar",
                    "color": "green",
                    "shape": "arrowUp",
                    "text": "Buy"
                })
            elif is_sell:
                markers.append({
                    "time": int(curr_row['time']),
                    "position": "aboveBar",
                    "color": "red",
                    "shape": "arrowDown",
                    "text": "Sell"
                })

        if markers:
            seriesCandlestickChart[0]["markers"] = markers

    return [
        {
            "chart": chartOptions,
            "series": seriesCandlestickChart
        }
    ]





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


@st.fragment(run_every=5)
def run_trading_loop(selected_option):
    # If running, use the running strategy. If not, create a temporary one just for viewing!
    strat = st.session_state.strategy
    is_view_only = False

    if not strat and selected_option and st.session_state.logged_in:
        # Create a view-only strategy controller
        strat = StrategyController(
            st.session_state.api, selected_option['tsym'], selected_option['token'], selected_option['exch'],
            "BUY", True, 0, 0, 0, 0, interval_val
        )
        is_view_only = True

    if strat:
        df = strat.fetch_and_calculate()

        col1, col2 = st.columns([3, 1])
        with col1:
            # We add a small custom HTML overlay to serve as a custom legend

            if not df.empty:
                if not is_view_only:
                    strat.evaluate_signals(df)

                # Render checkboxes above chart
                c_leg = st.columns(6)
                with c_leg[0]:
                    st.markdown(f"**{strat.symbol}**")
                    st.markdown(f"**{chart_interval}**")
                with c_leg[1]:
                    st.session_state.show_ema_9 = st.checkbox("9 EMA", value=st.session_state.show_ema_9)
                with c_leg[2]:
                    st.session_state.show_ema_25 = st.checkbox("25 EMA", value=st.session_state.show_ema_25)
                with c_leg[3]:
                    st.session_state.show_ema_50 = st.checkbox("50 EMA L", value=st.session_state.show_ema_50)
                with c_leg[4]:
                    st.session_state.show_ema_250 = st.checkbox("250 EMA", value=st.session_state.show_ema_250)
                with c_leg[5]:
                    st.session_state.show_vwap = st.checkbox("VWAP", value=st.session_state.show_vwap)

                chart_options = render_chart(df, strat.symbol, chart_interval)
                if chart_options:
                    renderLightweightCharts(chart_options, 'live_chart')
            else:
                st.warning(f"Waiting for candlestick data... (API returned empty data for token {strat.token})")

        with col2:
            if not is_view_only:
                st.markdown("### Bot Running 🟢")
            else:
                st.markdown("### View Mode 🟡")

            if not df.empty:
                latest_close = df.iloc[-1]['close']
                st.metric("Last Traded Price", f"₹ {latest_close:.2f}")
                if not is_view_only:
                    st.metric("Live Running P&L", f"₹ {strat.running_pnl:.2f}")
            else:
                st.metric("Last Traded Price", "---")

        # Show tables
        st.subheader("Trade Logs")
        logs = get_trade_logs(20)
        if logs:
            # Play a notification beep if a new log was added
            if 'last_log_count' not in st.session_state:
                st.session_state.last_log_count = len(logs)
            elif len(logs) > st.session_state.last_log_count:
                st.markdown('<audio autoplay style="display:none"><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)
                st.session_state.last_log_count = len(logs)

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
    else:
        st.info("Please login and select an index to view live charts.")

run_trading_loop(selected_option)

st.subheader("System Logs (Live API Debug)")
if st.session_state.system_logs:
    log_text = "\n".join(st.session_state.system_logs[::-1])
    st.markdown(f'<div style="height: 200px; overflow-y: scroll; background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 12px; white-space: pre-wrap;">{log_text}</div>', unsafe_allow_html=True)
