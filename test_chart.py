import streamlit as st
import time
import random
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(layout="wide")
st.title("Real-Time Candle Updates")

chartOptions = {
    "layout": {"textColor": 'black', "background": {"type": 'solid', "color": 'white'}},
    "grid": {"vertLines": {"color": '#f0f3fa'}, "horzLines": {"color": '#f0f3fa'}},
}

if "historical_data" not in st.session_state:
    st.session_state.historical_data = [
        {"time": 1723284000, "open": 100, "high": 105, "low": 98, "close": 103},
        {"time": 1723284060, "open": 103, "high": 106, "low": 102, "close": 105},
    ]

@st.fragment(run_every=2)
def update_chart():
    price_change = random.uniform(-0.5, 0.5)
    last_candle = st.session_state.historical_data[-1]

    current_close = last_candle['close'] + price_change

    st.session_state.historical_data[-1] = {
        "time": last_candle['time'],
        "open": last_candle['open'],
        "high": max(last_candle['high'], current_close),
        "low": min(last_candle['low'], current_close),
        "close": current_close
    }

    seriesCandlestickChart = [{
        "type": 'Candlestick',
        "data": st.session_state.historical_data,
        "options": {
            "upColor": '#26a69a', "downColor": '#ef5350',
            "borderVisible": False, "wickVisible": True
        }
    }]

    renderLightweightCharts([
        {
            "chart": chartOptions,
            "series": seriesCandlestickChart
        }
    ], key="live_trading_chart")

update_chart()
