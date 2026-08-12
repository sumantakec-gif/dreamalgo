import streamlit as st

# Force IPv4 for all outbound connections
import socket
if not hasattr(socket, '_patched'):
    old_getaddrinfo = socket.getaddrinfo

    def new_getaddrinfo(*args, **kwargs):
        responses = old_getaddrinfo(*args, **kwargs)
        return [response for response in responses if response[0] == socket.AF_INET]

    socket.getaddrinfo = new_getaddrinfo
    socket._patched = True


import pandas as pd
import time
from src.trading.api import FlattradeClient
from src.trading.strategy import StrategyController
from src.database.crud import get_trade_logs, get_order_reports, save_user_config, get_user_config, get_today_pnl
from io import BytesIO
from streamlit_option_menu import option_menu


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







# Fetch Quote details early to populate Header and strike dropdown
nifty_quote = None
sensex_quote = None
ltp = None
if st.session_state.logged_in:
    nifty_quote = st.session_state.api.get_index_quote_details("NIFTY")
    sensex_quote = st.session_state.api.get_index_quote_details("SENSEX")

# Build Header UI
header_col1, header_col2 = st.columns([1.5, 3])
with header_col1:
    st.title("DreamAlgo")
with header_col2:
    if st.session_state.logged_in and nifty_quote and sensex_quote:
        n_lp, n_pc = nifty_quote['lp'], nifty_quote['pc']
        s_lp, s_pc = sensex_quote['lp'], sensex_quote['pc']

        n_chg = n_lp - n_pc
        n_col = "green" if n_chg >= 0 else "red"
        n_sgn = "+" if n_chg >= 0 else ""

        s_chg = s_lp - s_pc
        s_col = "green" if s_chg >= 0 else "red"
        s_sgn = "+" if s_chg >= 0 else ""

        today_pnl = get_today_pnl()
        pnl_col = "green" if today_pnl >= 0 else "red"
        pnl_sgn = "+" if today_pnl >= 0 else ""

        st.markdown(
            f"<div style='text-align: right; padding-top: 25px; white-space: nowrap;'>"
            f"<span style='margin-right: 15px;'><b>NIFTY</b>: ₹{n_lp:.2f} "
            f"(<span style='color: {n_col};'>{n_sgn}{n_chg:.2f}</span>)</span>"
            f"<span style='margin-right: 15px;'><b>SENSEX</b>: ₹{s_lp:.2f} "
            f"(<span style='color: {s_col};'>{s_sgn}{s_chg:.2f}</span>)</span>"
            f"<span><b>Today's P&L</b>: <span style='color: {pnl_col};'>₹{pnl_sgn}{today_pnl:.2f}</span></span>"
            f"</div>",
            unsafe_allow_html=True
        )

# Sidebar
with st.sidebar:
    menu_selection = option_menu(
        "Menu",
        ["Broker", "Practice", "Algo", "Historical Chart"],
        icons=['building', 'play-circle', 'robot', 'bar-chart-line'],
        menu_icon="cast",
        default_index=0
    )
    st.markdown("---")

    if menu_selection == "Broker":
        st.info("Broker setup is in the main window.")

    elif menu_selection in ["Practice", "Algo"]:
        st.header(f"{menu_selection} Settings")

        lot_price_min = st.number_input("Lot Price Min", value=50.0)
        lot_price_max = st.number_input("Lot Price Max", value=200.0)
        mode = st.selectbox("Mode", ["BUY", "SELL"])

        is_paper = st.checkbox("Paper Trade", value=True)
        qty = st.number_input("Lot Size / Quantity", value=50)
        investment = st.number_input("Total Amount to Invest", value=100000)
        target_pts = st.number_input("Target (Points)", value=20)
        sl_pts = st.number_input("Stoploss (Points)", value=10)

    elif menu_selection == "Historical Chart":
        st.header("Historical Chart")
        st.info("Historical view placeholder. Navigate back to Algo or Practice to run the bot.")
        is_paper = True

if menu_selection != 'Broker':
    # Chart Controls (Decoupled from Algo Running state)
    col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)
    with col_c1:
        index_name = st.selectbox("Index", ["NIFTY", "SENSEX"], key="selected_index")

    if st.session_state.logged_in:
        if index_name == "NIFTY" and nifty_quote:
            ltp = nifty_quote['lp']
        elif index_name == "SENSEX" and sensex_quote:
            ltp = sensex_quote['lp']

    with col_c2:
        opt_type = st.selectbox("Option Type (CE/PE)", ["CE", "PE"])

    with col_c3:
        expiry_options = ["Login to fetch expiries"]
        if st.session_state.logged_in and ltp:
            available_expiries = st.session_state.api.get_available_expiries(index_name)
            if available_expiries:
                expiry_options = available_expiries
        expiry_selection = st.selectbox("Expiry", expiry_options)

    with col_c4:
        if ltp:
            round_val = 50 if index_name == 'NIFTY' else 100
            atm_strike = round(ltp / round_val) * round_val
            spot_options = []
            for i in range(-20, 21):
                spot_options.append(str(atm_strike + (i * round_val)))

            # Set default to ATM
            default_index = spot_options.index(str(atm_strike))
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
else:
    interval_val = 1
    selected_option = None




# Generate the option config dynamically
selected_option = None
if st.session_state.logged_in and ltp:
    try:
        selected_strike = int(strike_selection)
    except ValueError:
        round_val = 50 if index_name == 'NIFTY' else 100
        atm_strike = round(ltp / round_val) * round_val
        if "Login" in strike_selection:
            selected_strike = atm_strike
        elif strike_selection == "ATM":
            selected_strike = atm_strike
        else:
            offset_str = strike_selection.split(" ")[1]
            offset = int(offset_str)
            selected_strike = atm_strike + (offset * round_val) if opt_type == 'CE' else atm_strike - (offset * round_val)

    is_next_expiry = expiry_selection == "Next Expiry"
    target_date_str = None
    if expiry_selection not in ["Current Expiry", "Next Expiry"]:
        target_date_str = expiry_selection

    # We need lot_price_min / lot_price_max to safely fetch options even in view mode
    lp_min = lot_price_min if 'lot_price_min' in locals() else 50.0
    lp_max = lot_price_max if 'lot_price_max' in locals() else 200.0

    selected_option = st.session_state.api.get_nearest_expiry_option(
        index_name, opt_type, selected_strike, lp_min, lp_max,
        next_expiry=is_next_expiry, target_date_str=target_date_str
    )

if 'menu_selection' in locals() and menu_selection in ["Practice", "Algo"]:
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



import plotly.graph_objects as go
import json

def render_chart(df, script_name='Options Algo Chart', timeframe='1 Min'):
    if df.empty:
        return None

    plot_df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(plot_df['timestamp']):
        plot_df['timestamp'] = pd.to_datetime(plot_df['timestamp'])

    fig = go.Figure()

    # Main Candlestick
    fig.add_trace(go.Candlestick(
        x=plot_df['timestamp'],
        open=plot_df['open'],
        high=plot_df['high'],
        low=plot_df['low'],
        close=plot_df['close'],
        name='Price'
    ))

    # Add EMAs and VWAP
    if 'ema_9' in plot_df and st.session_state.show_ema_9:
        fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['ema_9'], mode='lines', name='9 EMA', line=dict(color='purple', width=1.5)))

    if 'ema_25' in plot_df and st.session_state.show_ema_25:
        fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['ema_25'], mode='lines', name='25 EMA', line=dict(color='green', width=1.5)))

    if 'ema_50_low' in plot_df and st.session_state.show_ema_50:
        fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['ema_50_low'], mode='lines', name='50 EMA Low', line=dict(color='blue', width=1.5)))

    if 'ema_250' in plot_df and st.session_state.show_ema_250:
        fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['ema_250'], mode='lines', name='250 EMA', line=dict(color='orange', width=2)))

    if 'vwap' in plot_df and st.session_state.show_vwap:
        fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['vwap'], mode='lines', name='VWAP', line=dict(color='darkred', width=1.5)))

    # Markers for crossovers
    if 'ema_9' in plot_df:
        buy_times, buy_prices = [], []
        sell_times, sell_prices = [], []

        for i in range(1, len(plot_df)):
            prev_row = plot_df.iloc[i-1]
            curr_row = plot_df.iloc[i]

            if pd.isna(prev_row['ema_9']) or pd.isna(curr_row['ema_9']):
                continue

            is_buy = prev_row['close'] <= prev_row['ema_9'] and curr_row['close'] > curr_row['ema_9']
            is_sell = prev_row['close'] >= prev_row['ema_9'] and curr_row['close'] < curr_row['ema_9']

            if is_buy:
                buy_times.append(curr_row['timestamp'])
                buy_prices.append(curr_row['low'] - (curr_row['high'] - curr_row['low']) * 0.1) # below bar
            elif is_sell:
                sell_times.append(curr_row['timestamp'])
                sell_prices.append(curr_row['high'] + (curr_row['high'] - curr_row['low']) * 0.1) # above bar

        if buy_times:
            fig.add_trace(go.Scatter(
                x=buy_times, y=buy_prices, mode='markers', name='Buy Signal',
                marker=dict(symbol='triangle-up', size=10, color='green')
            ))

        if sell_times:
            fig.add_trace(go.Scatter(
                x=sell_times, y=sell_prices, mode='markers', name='Sell Signal',
                marker=dict(symbol='triangle-down', size=10, color='red')
            ))

    fig.update_layout(
        title=script_name,
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0),
        height=500,
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig





# Main Area

def render_broker_connection():
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
        if st.button("Disconnect Broker", key="disconnect_main"):
            import os
            if os.path.exists(".flattrade_session.json"):
                os.remove(".flattrade_session.json")
            st.session_state.api = None
            st.session_state.logged_in = False
            st.session_state.running = False
            st.session_state.strategy = None
            st.query_params.clear()
            st.rerun()


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

        cached_session = load_session_cache()
        saved_token = cached_session['token'] if cached_session else "No token saved"
        st.text_input("Saved Flattrade Token (Read-Only)", value=saved_token, disabled=True)

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

                fig = render_chart(df, strat.symbol, chart_interval)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key="live_trading_chart")
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

if menu_selection != 'Broker':
    opt = selected_option if "selected_option" in locals() else None
    run_trading_loop(opt)
else:
    render_broker_connection()

st.subheader("System Logs (Live API Debug)")
if st.session_state.system_logs:
    log_text = "\n".join(st.session_state.system_logs[::-1])
    st.markdown(f'<div style="height: 200px; overflow-y: scroll; background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 12px; white-space: pre-wrap;">{log_text}</div>', unsafe_allow_html=True)
