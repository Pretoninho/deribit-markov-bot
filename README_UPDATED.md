# Deribit Markov Regime Switching Bot

A real-time cryptocurrency trading bot with **Hidden Markov Model (HMM)** regime detection for Deribit exchange.

## 🎯 Features

- **Live WebSocket Data Feed**: Real-time price updates from Deribit API
- **Markov Regime Detection**: Automatic volatility regime classification (LOW, MEDIUM, HIGH)
- **Web Dashboard**: Responsive Flask + HTML/JS interface
- **OHLC Bars**: 5-second candlestick aggregation with regime labeling
- **Historical Calibration**: Auto-calibration from recent market data
- **Testnet/Mainnet Support**: Switch between demo and live trading

## 📊 Architecture

```
├── app_flask.py          # Flask backend with WebSocket support
├── markov_model.py       # HMM regime detection algorithm
├── templates/
│   └── index.html        # Web interface
├── deribit_markov_bot.py # Original Tkinter version (legacy)
└── streamlit_app.py      # Streamlit version (legacy)
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd /workspaces/deribit-markov-bot
source venv/bin/activate
pip install -r requirements_deribit.txt
```

### 2. Run the Application
```bash
python3 app_flask.py
```

### 3. Open Dashboard
Navigate to: **http://localhost:5000**

## 📈 How It Works

### Markov Regime Detection

The bot uses a **3-state Hidden Markov Model** to classify market regimes:

| Regime | Volatility | Characteristics |
|--------|-----------|-----------------|
| **LOW** (0) | < 0.5% | Mean-reverting, low noise |
| **MEDIUM** (1) | 0.5-1.5% | Trending markets |
| **HIGH** (2) | > 1.5% | Volatile, breakouts |

**Key Algorithm**: Viterbi algorithm for optimal state sequence detection

### OHLC Bar Generation
- **Timeframe**: 5 seconds
- **Calculation**: Open/High/Low/Close + volatility metric
- **Regime Update**: Applied to most recent bar based on historical patterns

### Historical Calibration
- Loads last 5 minutes of data on stream start
- Calculates volatility percentiles (P25, P75) for thresholds
- Trains transition matrix from observed patterns

## 🎛️ Web Interface

### Control Panel (Sidebar)
- **Environment**: Select testnet or mainnet
- **Connect/Disconnect**: Manage Deribit connection
- **Asset Selection**: Choose BTC or ETH
- **Instrument Type**: Futures or options
- **Stream Control**: Start/stop data collection

### Dashboard (Main)
- **Status Indicator**: Connection state
- **Price Metrics**: Last Price, Bid, Ask
- **Live Chart**: Price updates over time
- **Auto-refresh**: Updates every 500ms

## 🔌 API Endpoints

### Connection
- `POST /api/connect` - Connect to Deribit
- `POST /api/disconnect` - Close connection
- `GET /api/status` - Get current status

### Data
- `GET /api/instruments/<currency>/<kind>` - List available instruments
- `GET /api/price-history` - Get recent prices
- `GET /api/chart-data` - Get OHLC bars with regimes

### Streaming
- `POST /api/subscribe` - Start ticker subscription
- `POST /api/unsubscribe` - Stop ticker subscription
- WebSocket `price_update` - Real-time price events

## 🛠️ Configuration

Edit in `app_flask.py` or `markov_model.py`:

```python
# OHLC bar duration (seconds)
self.bar_duration = 5

# Volatility thresholds (auto-calibrated)
self.vol_thresholds = [0.005, 0.015]  # LOW/MEDIUM, MEDIUM/HIGH

# Transition matrix (state persistence)
self.transition_matrix = np.array([
    [0.70, 0.20, 0.10],  # From LOW
    [0.25, 0.60, 0.15],  # From MEDIUM
    [0.10, 0.25, 0.65]   # From HIGH
])
```

## 📊 Example Output

```
✓ Connected to Deribit testnet
✓ Subscribed to BTC-PERPETUAL
✓ Model calibrated with 60 bars
  Volatility thresholds: LOW=0.0043, HIGH=0.0156

[OHLC Bar]
Time: 10:42:15
Open: 42850.50
High: 42865.30
Low: 42845.20
Close: 42860.75
Volatility: 0.47%
Regime: MEDIUM (Confidence: 85%)
Next Regime: HIGH (60% probability)
```

## 🔐 Testnet Credentials

By default, the bot connects to Deribit **testnet** (no real money):
- Base URL: `https://test.deribit.com/api/v2`
- WebSocket: `wss://test.deribit.com/ws/api/v2`

To use mainnet, select from dashboard or set `testnet=False` in code.

## 📦 Dependencies

- **websocket-client**: WebSocket protocol client
- **requests**: HTTP library
- **flask**: Web framework
- **flask-socketio**: Real-time communication
- **numpy/scipy**: Numerical computing & statistics
- **matplotlib**: Charting (legacy)
- **streamlit/plotly**: Alternative UIs (legacy)

## 🐛 Troubleshooting

### "Connection timeout"
- Check internet connection
- Verify Deribit API is accessible
- Try testnet instead of mainnet

### "No instruments found"
- Asset/type combination may not exist
- Manually verify on deribit.com

### "No display name" (Tkinter error)
- Use Flask app instead: `python3 app_flask.py`
- Original Tkinter requires X11 display

## 📝 License

MIT License - See LICENSE file

## 🚀 Future Enhancements

- [ ] Trading signal generation
- [ ] Portfolio balancing
- [ ] Strategy backtesting framework
- [ ] Advanced regime prediction
- [ ] Alert system
- [ ] Database persistence
- [ ] Docker containerization

## 📧 Support

For issues or questions, open a GitHub issue or contact the project owner.
