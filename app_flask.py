"""
Flask backend for Deribit Markov Bot with WebSocket support
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import threading
import time
from datetime import datetime, timedelta
from collections import deque
import websocket
import json
import requests
import warnings
import numpy as np
from markov_model import MarkovRegime, OHLCBar

warnings.filterwarnings("ignore")

app = Flask(__name__, template_folder='templates')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Store clients for broadcasting
connected_clients = set()

def emit_event(event, data):
    """Emit event to all connected clients"""
    thr = threading.Thread(target=lambda: socketio.emit(event, data, broadcast=True, namespace='/'))
    thr.daemon = True
    thr.start()

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
        self.ohlc_bars = deque(maxlen=50)
        self.current_bar = None
        self.bar_start_time = None
        self.bar_duration = 5  # 5 seconds
        self.regime_model = MarkovRegime()
        self.streaming = False
        self.lock = threading.Lock()

    def connect(self):
        """Connect to Deribit WebSocket"""
        try:
            self.running = True
            ws_thread = threading.Thread(target=self._ws_connect, daemon=True)
            ws_thread.start()
            
            for _ in range(50):
                if self.connected:
                    emit_event('connection_status', {
                        'status': 'connected',
                        'env': 'testnet' if self.testnet else 'mainnet',
                        'message': f'Connected to Deribit {("testnet" if self.testnet else "mainnet")}'
                    })
                    return True
                time.sleep(0.1)
            
            emit_event('connection_status', {
                'status': 'error',
                'message': 'Connection timeout'
            })
            return False
        except Exception as e:
            emit_event('connection_status', {
                'status': 'error',
                'message': str(e)
            })
            return False

    def _ws_connect(self):
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
            print(f"WebSocket error: {e}")
            self.connected = False

    def _on_ws_open(self, ws):
        self.connected = True
        print("✓ WebSocket connected")

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'params' in data and 'data' in data['params']:
                ticker_data = data['params']['data']
                
                # Validate required fields
                if 'last_price' not in ticker_data:
                    return
                
                price = ticker_data.get('last_price')
                bid = ticker_data.get('best_bid_price', price)
                ask = ticker_data.get('best_ask_price', price)
                
                # Validate price values
                if not isinstance(price, (int, float)) or price <= 0:
                    print(f"⚠ Invalid price value: {price}")
                    return
                
                if not isinstance(bid, (int, float)) or bid <= 0:
                    bid = price
                if not isinstance(ask, (int, float)) or ask <= 0:
                    ask = price
                
                with self.lock:
                    self.last_price = price
                    self.bid_price = bid
                    self.ask_price = ask
                    self.price_history.append((datetime.now(), price))
                    
                    # Update OHLC bar
                    if self.current_bar is None:
                        self.current_bar = OHLCBar(datetime.now(), price)
                        self.bar_start_time = datetime.now()
                    else:
                        elapsed = (datetime.now() - self.bar_start_time).total_seconds()
                        if elapsed >= self.bar_duration:
                            # New bar
                            self.ohlc_bars.append(self.current_bar)
                            if len(self.ohlc_bars) >= 3:
                                regime = self.regime_model.get_regime(list(self.ohlc_bars))
                                self.current_bar.regime = regime
                            
                            self.current_bar = OHLCBar(datetime.now(), price)
                            self.bar_start_time = datetime.now()
                        else:
                            self.current_bar.update(price)
                    
                    # Emit price update
                    emit_event('price_update', {
                        'price': price,
                        'bid': bid,
                        'ask': ask,
                        'timestamp': datetime.now().isoformat(),
                        'spread': ask - bid
                    })
        except json.JSONDecodeError as e:
            print(f"⚠ Invalid JSON message: {e}")
        except Exception as e:
            print(f"⚠ Message processing error: {e}")

    def _on_ws_error(self, ws, error):
        print(f"WebSocket error: {error}")
        emit_event('connection_status', {
            'status': 'error',
            'message': str(error)
        })

    def _on_ws_close(self, ws, close_status_code, close_msg):
        self.connected = False
        print("WebSocket closed")

    def subscribe_ticker(self, symbol):
        if not self.connected or not self.ws:
            return False
        try:
            self.current_symbol = symbol
            self.ohlc_bars.clear()
            self.current_bar = None
            self.bar_start_time = None
            self.price_history.clear()
            
            subscribe_msg = {
                "jsonrpc": "2.0",
                "method": "public/subscribe",
                "id": 1,
                "params": {"channels": [f"ticker.{symbol}.raw"]}
            }
            self.ws.send(json.dumps(subscribe_msg))
            self.streaming = True
            
            emit_event('subscription_status', {
                'status': 'subscribed',
                'symbol': symbol,
                'message': f'Subscribed to {symbol}'
            })
            return True
        except Exception as e:
            emit_event('subscription_status', {
                'status': 'error',
                'message': str(e)
            })
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
            self.streaming = False
            self.current_symbol = None
        except Exception as e:
            print(f"Unsubscribe error: {e}")

    def get_instruments(self, currency, kind):
        """Get available instruments from Deribit API"""
        try:
            params = {"currency": currency, "kind": kind, "expired": False}
            response = requests.get(
                f"{self.base_url}/public/get_instruments",
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ API Error {response.status_code}: {response.text[:200]}")
                return []
            
            data = response.json()
            if 'result' not in data:
                print(f"✗ Invalid response format: missing 'result' key")
                return []
            
            result = data['result']
            if not isinstance(result, list):
                print(f"✗ Invalid result format: expected list, got {type(result)}")
                return []
            
            instruments = [inst.get('instrument_name') for inst in result if 'instrument_name' in inst]
            print(f"✓ Retrieved {len(instruments)} instruments for {currency}/{kind}")
            return instruments
            
        except requests.Timeout:
            print(f"✗ Request timeout while fetching instruments")
            return []
        except requests.RequestException as e:
            print(f"✗ Network error: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON response: {e}")
            return []
        except Exception as e:
            print(f"✗ Unexpected error getting instruments: {e}")
            return []

    def get_historical_data(self, symbol):
        """Get historical OHLC data from Deribit"""
        try:
            # Timestamps in milliseconds (Deribit requirement)
            now_ms = int(datetime.now().timestamp() * 1000)
            start_ms = int((datetime.now() - timedelta(seconds=300)).timestamp() * 1000)
            
            params = {
                "instrument_name": symbol,
                "start_timestamp": start_ms,
                "end_timestamp": now_ms,
                "resolution": "5"  # 5-second bars
            }
            
            response = requests.get(
                f"{self.base_url}/public/get_tradingview_chart_data",
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ API Error {response.status_code}: {response.text[:200]}")
                return []
            
            data = response.json()
            if 'result' not in data:
                print(f"✗ Invalid response format: missing 'result' key")
                return []
            
            result = data['result']
            if not result:
                print(f"⚠ No historical data available for {symbol}")
                return []
            
            # Validate OHLC structure
            required_keys = ['o', 'h', 'l', 'c']
            for key in required_keys:
                if key not in result:
                    print(f"✗ Invalid OHLC data: missing '{key}' key")
                    return []
            
            # Build bar objects
            bars = []
            for i in range(len(result.get('o', []))):
                try:
                    bar = {
                        'o': result['o'][i],
                        'h': result['h'][i],
                        'l': result['l'][i],
                        'c': result['c'][i],
                        'v': result.get('v', [0])[i] if 'v' in result else 0,
                        't': result.get('ticks', [])[i] if 'ticks' in result else None
                    }
                    bars.append(bar)
                except (IndexError, KeyError) as e:
                    print(f"⚠ Error processing bar {i}: {e}")
            
            print(f"✓ Retrieved {len(bars)} historical bars for {symbol}")
            return bars
            
        except requests.Timeout:
            print(f"✗ Request timeout while fetching historical data")
            return []
        except requests.RequestException as e:
            print(f"✗ Network error: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON response: {e}")
            return []
        except Exception as e:
            print(f"✗ Unexpected error getting historical data: {e}")
            return []

    def disconnect(self):
        self.running = False
        self.streaming = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        self.connected = False

# Global Deribit app instance
g_deribit = None

# API Routes
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/api/connect', methods=['POST'])
def api_connect():
    global g_deribit
    data = request.json
    testnet = data.get('testnet', True)
    
    print(f"Connect request: testnet={testnet}")
    
    # Check if we need a new instance
    if g_deribit is None or g_deribit.testnet != testnet:
        print("Creating new DeribitApp instance")
        if g_deribit:
            g_deribit.disconnect()
        g_deribit = DeribitApp(testnet=testnet)
    
    if g_deribit.connect():
        print("✓ Connection successful")
        return jsonify({'status': 'connected', 'env': 'testnet' if testnet else 'mainnet'}), 200
    else:
        print("✗ Connection failed")
        return jsonify({'status': 'failed', 'error': 'Connection timeout or failed'}), 400

@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    global g_deribit
    if g_deribit:
        g_deribit.disconnect()
    return jsonify({'status': 'disconnected'}), 200

@app.route('/api/status', methods=['GET'])
def api_status():
    global g_deribit
    if g_deribit is None:
        return jsonify({
            'connected': False,
            'streaming': False,
            'symbol': None,
            'price': None
        }), 200
    
    return jsonify({
        'connected': g_deribit.connected,
        'streaming': g_deribit.streaming,
        'symbol': g_deribit.current_symbol,
        'price': g_deribit.last_price,
        'bid': g_deribit.bid_price,
        'ask': g_deribit.ask_price
    }), 200

@app.route('/api/instruments/<currency>/<kind>', methods=['GET'])
def api_instruments(currency, kind):
    global g_deribit
    if g_deribit is None:
        print(f"ERROR: g_deribit is None when requesting {currency}/{kind}")
        return jsonify({'error': 'Not connected', 'instruments': []}), 200
    
    if not g_deribit.connected:
        print(f"ERROR: g_deribit not connected when requesting {currency}/{kind}")
        return jsonify({'error': 'Connection lost', 'instruments': []}), 200
    
    print(f"Getting instruments: {currency}/{kind}")
    try:
        instruments = g_deribit.get_instruments(currency, kind)
        print(f"Returned {len(instruments)} instruments")
        return jsonify(instruments), 200
    except Exception as e:
        print(f"ERROR getting instruments: {e}")
        return jsonify({'error': str(e), 'instruments': []}), 500

@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    global g_deribit
    data = request.json
    symbol = data.get('symbol')
    
    if g_deribit is None:
        return jsonify({'status': 'error', 'message': 'Not connected'}), 400
    
    if g_deribit.subscribe_ticker(symbol):
        return jsonify({'status': 'subscribed'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Subscribe failed'}), 400

@app.route('/api/unsubscribe', methods=['POST'])
def api_unsubscribe():
    global g_deribit
    data = request.json
    symbol = data.get('symbol')
    
    if g_deribit:
        g_deribit.unsubscribe_ticker(symbol)
    
    return jsonify({'status': 'unsubscribed'}), 200

@app.route('/api/chart-data', methods=['GET'])
def api_chart_data():
    global g_deribit
    if g_deribit is None:
        return jsonify([]), 200
    
    with g_deribit.lock:
        bars = list(g_deribit.ohlc_bars)
        if g_deribit.current_bar:
            bars.append(g_deribit.current_bar)
        
        chart_data = [
            {
                'time': bar.timestamp.isoformat(),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'regime': bar.regime,
                'ticks': bar.tick_count
            }
            for bar in bars
        ]
    
    return jsonify(chart_data), 200

@app.route('/api/price-history', methods=['GET'])
def api_price_history():
    global g_deribit
    if g_deribit is None:
        return jsonify([]), 200
    
    with g_deribit.lock:
        data = [
            {'time': t.isoformat(), 'price': p}
            for t, p in list(g_deribit.price_history)
        ]
    
    return jsonify(data), 200

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print("Client connected")
    emit('connect_response', {'data': 'Connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
