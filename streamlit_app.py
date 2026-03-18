import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import threading
import time
from datetime import datetime, timedelta
from collections import deque
import websocket
import json
import requests
from dataclasses import dataclass
import warnings
warnings.filterwarnings("ignore")

# Page config
st.set_page_config(
    page_title="Deribit Markov Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS styling
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 24px; }
    .main { background-color: #0d1117; }
    h1, h2, h3 { color: #58a6ff; }
</style>
""", unsafe_allow_html=True)

@dataclass
class OHLCBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    tick_count: int = 1
    regime: int = 0
    
    def update(self, price):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.tick_count += 1
    
    @property
    def volatility(self):
        return (self.high - self.low) / self.close if self.close > 0 else 0

class DeribitApp:
    def __init__(self, testnet=True):
        self.connected = False
        self.testnet = testnet
        self.base_url = "https://test.deribit.com/api/v2" if testnet else "https://www.deribit.com/api/v2"
        self.ws_url = "wss://test.deribit.com/ws/api/v2" if testnet else "wss://www.deribit.com/ws/api/v2"
        self.ws = None
        self.running = False
        self.last_price = None
        self.bid_price = None
        self.ask_price = None
        self.current_symbol = None
        self.price_history = deque(maxlen=1000)
        self.price_callback = None

    def connect(self):
        try:
            self.running = True
            def ws_connect():
                try:
                    self.ws = websocket.WebSocketApp(
                        self.ws_url,
                        on_open=self._on_ws_open,
                        on_message=self._on_ws_message,
                        on_error=self._on_ws_error,
                        on_close=self._on_ws_close
                    )
                    self.ws.run_forever()
                except Exception as e:
                    st.error(f"WebSocket error: {e}")
                    self.connected = False
            
            ws_thread = threading.Thread(target=ws_connect, daemon=True)
            ws_thread.start()
            
            for _ in range(50):
                if self.connected:
                    return True
                time.sleep(0.1)
            return False
        except Exception as e:
            st.error(f"Connection error: {e}")
            return False

    def _on_ws_open(self, ws):
        self.connected = True

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'params' in data and 'data' in data['params']:
                ticker_data = data['params']['data']
                price = ticker_data.get('last_price')
                bid = ticker_data.get('best_bid_price')
                ask = ticker_data.get('best_ask_price')
                if price and price > 0:
                    self.last_price = price
                    self.bid_price = bid or price
                    self.ask_price = ask or price
                    self.price_history.append((datetime.now(), price))
                    if self.price_callback:
                        self.price_callback(price)
        except Exception as e:
            pass

    def _on_ws_error(self, ws, error):
        st.warning(f"WebSocket error: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        self.connected = False

    def subscribe_ticker(self, symbol):
        if not self.connected or not self.ws:
            return False
        try:
            self.current_symbol = symbol
            subscribe_msg = {
                "jsonrpc": "2.0",
                "method": "public/subscribe",
                "id": 1,
                "params": {"channels": [f"ticker.{symbol}.raw"]}
            }
            self.ws.send(json.dumps(subscribe_msg))
            return True
        except Exception as e:
            st.error(f"Subscribe error: {e}")
            return False

    def unsubscribe_ticker(self, symbol):
        if not self.connected or not self.ws:
            return
        try:
            unsubscribe_msg = {
                "jsonrpc": "2.0",
                "method": "public/unsubscribe",
                "id": 1,
                "params": {"channels": [f"ticker.{symbol}.raw"]}
            }
            self.ws.send(json.dumps(unsubscribe_msg))
        except Exception as e:
            pass

    def get_historical_data(self, symbol, timeframe="5"):
        try:
            params = {
                "instrument_name": symbol,
                "start_timestamp": int((datetime.now() - timedelta(seconds=300)).timestamp() * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "resolution": timeframe
            }
            response = requests.get(
                f"{self.base_url}/public/get_tradingview_chart_data",
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    return [
                        {
                            'o': bar.get('open'),
                            'h': bar.get('high'),
                            'l': bar.get('low'),
                            'c': bar.get('close'),
                            't': bar.get('ticks', 0)
                        }
                        for bar in data['result']
                    ]
            return []
        except Exception as e:
            st.error(f"Historical data error: {e}")
            return []

    def get_instruments(self, currency, kind):
        try:
            params = {"currency": currency, "kind": kind, "expired": False}
            response = requests.get(
                f"{self.base_url}/public/get_instruments",
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    return [inst['instrument_name'] for inst in data['result']]
            return []
        except Exception as e:
            st.error(f"Instruments error: {e}")
            return []

    def disconnect(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        self.connected = False

# Initialize session state
if 'deribit' not in st.session_state:
    st.session_state.deribit = None
if 'bars' not in st.session_state:
    st.session_state.bars = deque(maxlen=20)
if 'current_bar' not in st.session_state:
    st.session_state.current_bar = None
if 'bar_start_time' not in st.session_state:
    st.session_state.bar_start_time = None
if 'streaming' not in st.session_state:
    st.session_state.streaming = False

# Title
st.title("📊 Deribit Regime Switching Bot")
st.markdown("Real-time Live Market Data with Markov Regime Detection")

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Control Panel")
    
    # Connection settings
    st.subheader("Connection")
    env = st.selectbox("Environment", ["testnet", "mainnet"], index=0)
    testnet = env == "testnet"
    
    col1, col2 = st.columns(2)
    with col1:
        connect_btn = st.button("🔗 Connect", use_container_width=True)
    with col2:
        disconnect_btn = st.button("🔌 Disconnect", use_container_width=True)
    
    if connect_btn:
        with st.spinner("Connecting to Deribit..."):
            if st.session_state.deribit is None:
                st.session_state.deribit = DeribitApp(testnet=testnet)
            if st.session_state.deribit.connect():
                st.success(f"✓ Connected to Deribit {env}")
            else:
                st.error("✗ Connection failed")
    
    if disconnect_btn:
        if st.session_state.deribit:
            st.session_state.deribit.disconnect()
            st.session_state.streaming = False
            st.success("✓ Disconnected")
    
    st.divider()
    
    # Instrument selection
    if st.session_state.deribit and st.session_state.deribit.connected:
        st.subheader("Select Instrument")
        
        col1, col2 = st.columns(2)
        with col1:
            asset = st.selectbox("Asset", ["BTC", "ETH"])
        with col2:
            kind = st.selectbox("Type", ["future", "option"])
        
        with st.spinner("Loading instruments..."):
            instruments = st.session_state.deribit.get_instruments(asset, kind)
        
        if instruments:
            symbol = st.selectbox("Instrument", instruments, index=0)
            
            col1, col2 = st.columns(2)
            with col1:
                start_btn = st.button("▶ Start Stream", use_container_width=True)
            with col2:
                stop_btn = st.button("⏹ Stop Stream", use_container_width=True)
            
            if start_btn:
                if st.session_state.deribit.subscribe_ticker(symbol):
                    st.session_state.streaming = True
                    st.success(f"✓ Streaming {symbol}")
            
            if stop_btn:
                if st.session_state.deribit.current_symbol:
                    st.session_state.deribit.unsubscribe_ticker(st.session_state.deribit.current_symbol)
                st.session_state.streaming = False
                st.info("⏹ Stream stopped")
        else:
            st.warning("No instruments found")
    else:
        st.info("Connect to Deribit first")

# Main content
if st.session_state.deribit and st.session_state.deribit.connected:
    # Status and price
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Status",
            "🟢 CONNECTED" if st.session_state.deribit.connected else "🔴 DISCONNECTED"
        )
    
    with col2:
        if st.session_state.deribit.last_price:
            st.metric("Last Price", f"${st.session_state.deribit.last_price:.2f}")
        else:
            st.metric("Last Price", "---")
    
    with col3:
        if st.session_state.deribit.bid_price:
            st.metric("Bid", f"${st.session_state.deribit.bid_price:.2f}")
        else:
            st.metric("Bid", "---")
    
    with col4:
        if st.session_state.deribit.ask_price:
            st.metric("Ask", f"${st.session_state.deribit.ask_price:.2f}")
        else:
            st.metric("Ask", "---")
    
    st.divider()
    
    # Charts
    if st.session_state.streaming and st.session_state.deribit.price_history:
        # Price history chart
        price_df = pd.DataFrame(
            [(t, p) for t, p in st.session_state.deribit.price_history],
            columns=['Time', 'Price']
        )
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=price_df['Time'],
            y=price_df['Price'],
            mode='lines+markers',
            name='Last Price',
            line=dict(color='#58a6ff', width=2),
            marker=dict(size=4)
        ))
        
        fig.update_layout(
            title=f"Live Price Feed - {st.session_state.deribit.current_symbol}",
            xaxis_title="Time",
            yaxis_title="Price ($)",
            hovermode='x unified',
            template='plotly_dark',
            height=400,
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Statistics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        prices = price_df['Price'].values
        with col1:
            st.metric("Current", f"${prices[-1]:.2f}")
        with col2:
            st.metric("High", f"${max(prices):.2f}")
        with col3:
            st.metric("Low", f"${min(prices):.2f}")
        with col4:
            st.metric("Change", f"${prices[-1] - prices[0]:.2f}")
        with col5:
            pct_change = ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] > 0 else 0
            st.metric("% Change", f"{pct_change:.2f}%")
    else:
        st.info("🔄 Connect and start streaming to see data")
else:
    st.warning("🔗 Please connect to Deribit in the sidebar first")

# Auto-refresh
st.markdown("""
<script>
    setTimeout(function() {
        window.location.reload();
    }, 2000);
</script>
""", unsafe_allow_html=True)
