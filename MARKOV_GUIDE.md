# Markov Regime Switching Bot - Complete Implementation Guide

## 🎯 Overview

Your Deribit bot now has **three complete interfaces**:

| Interface | Type | Status | Launch |
|-----------|------|--------|--------|
| **Flask Web** | REST + WebSocket | ✅ **ACTIVE** | `python3 app_flask.py` → http://localhost:5000 |
| **Tkinter GUI** | Desktop | ❌ Requires X11 | `python3 deribit_markov_bot.py` |
| **Streamlit** | Web App | ❌ Legacy | `streamlit run streamlit_app.py` |

---

## 🚀 Quick Start

### 1. Launch the Application
```bash
cd /workspaces/deribit-markov-bot
source venv/bin/activate
python3 app_flask.py
```

### 2. Open in Browser
Visit: **http://localhost:5000**

### 3. Connect & Stream
1. Click **Connect** (testnet by default)
2. Select **Asset** (BTC/ETH) → **Type** (futures/options) → **Instrument**
3. Click **Start Stream**
4. Watch live prices and regime changes in real-time

---

## 🧠 Markov Regime Model Explained

### What is it?

A **Hidden Markov Model (HMM)** that detects **market regimes** based on **volatility**:

```
┌─────────────────────────────────────────────┐
│       Market Volatility Analysis            │
├─────────────────────────────────────────────┤
│ Input: Individual price ticks every second  │
│         ↓                                    │
│ Process: Aggregate into 5-second OHLC bars │
│          ↓                                   │
│ Output: Regime classification (LOW/MED/HIGH)│
└─────────────────────────────────────────────┘
```

### The 3 States

| State | Name | Volatility | Market Behavior | Strategy |
|-------|------|-----------|-----------------|----------|
| **0** | LOW | < 0.5% | Mean-reverting, choppy | Buy dips, Sell rallies |
| **1** | MEDIUM | 0.5% - 1.5% | Trending, steady | Follow trend, Use stops |
| **2** | HIGH | > 1.5% | Volatile, breakouts | Wide stops, Risk-off |

### How It Works

**Step 1: Extract Volatility Feature**
```python
# For each 5-second bar
volatility = (high - low) / close

Example:
- Bar: O=42850, H=42865, L=42845, C=42860
- Vol = (42865 - 42845) / 42860 = 0.0047 = 0.47%
→ Regime: MEDIUM
```

**Step 2: Viterbi Algorithm**
```
Finds the most likely state sequence using:
- Emission probabilities: P(observation | state)
  How likely is this volatility given the state?
- Transition probabilities: P(state_t | state_t-1)
  How likely is state transition?

Result: Optimal state path maximizing likelihood
```

**Step 3: Predictive Transition Matrix**
```python
From LOW:  [70%, 20%, 10%] → (70% stay LOW, 20% go MEDIUM, 10% go HIGH)
From MEDIUM: [25%, 60%, 15%] → (60% stay MEDIUM)
From HIGH: [10%, 25%, 65%] → (65% stay HIGH)
```

### Calibration

When you start streaming:
1. **Download** last 5 minutes of historical data
2. **Calculate** volatility for each bar
3. **Determine** percentiles (P25, P75) as thresholds
4. **Train** regime parameters from observed patterns

```
Example Output:
✓ Model calibrated with 60 bars
  Volatility thresholds: LOW=0.0043, HIGH=0.0156
```

---

## 📊 Live Dashboard Features

### Control Panel (Left Sidebar)
- **Environment**: Switch testnet ↔ mainnet
- **Connect/Disconnect**: Manage API connection
- **Asset Selection**: BTC, ETH, etc.
- **Instrument Type**: Futures, Options
- **Stream Control**: Start/Stop real-time feed

### Dashboard (Right Side)
- **Status Indicator**: 🟢 CONNECTED or 🔴 DISCONNECTED
- **Four Metrics**:
  - Last Price: Current market price
  - Bid: Highest buy order
  - Ask: Lowest sell order
  - Spread: Bid-Ask difference
- **Live Chart**: Price history (last 50 updates)
- **Auto-refresh**: Updates every 500ms

---

## 📈 Example Trading Scenario

```
TIME: 10:42:15
─────────────────────────────────────────
OHLC Bar #42:
  Open:     42850.50
  High:     42865.30
  Low:      42845.20
  Close:    42860.75
  Vol:      0.47%

Regime Detection:
  Current Regime: MEDIUM (Confidence: 85%)
  Next Regime (60% prob): HIGH
  Predicted Move: Volatility increase likely

Trading Decision:
  ├─ Tighten stops (volatility rising)
  ├─ Reduce position size
  └─ Prepare for breakout

─────────────────────────────────────────
TIME: 10:42:20
─────────────────────────────────────────
OHLC Bar #43:
  Vol:      1.62%

Regime Update:
  Current Regime: HIGH ← Transitioned!
  Market Signal: Volatility confirmed
  Action: Exit/Reduce if not directional
```

---

## 🔧 Advanced Configuration

### Edit Regime Parameters

**File:** `markov_model.py`

```python
class MarkovRegime:
    def __init__(self, n_states=3):
        # Change volatility thresholds
        self.vol_thresholds = [0.005, 0.015]  # Currently: 0.5%, 1.5%
        
        # Modify transition probabilities (more persistence)
        self.transition_matrix = np.array([
            [0.80, 0.15, 0.05],  # Stay in LOW longer
            [0.20, 0.70, 0.10],  # More stable
            [0.05, 0.20, 0.75]   # Stay in HIGH longer
        ])
        
        # Regime volatility characteristics
        regime_means = [0.003, 0.008, 0.020]  # Expected vol per state
        regime_stds = [0.001, 0.003, 0.010]   # Variability
```

### Change OHLC Bar Duration

**File:** `app_flask.py`

```python
self.bar_duration = 5  # Change from 5 seconds to:
#  self.bar_duration = 10  # 10 seconds
#  self.bar_duration = 1   # 1 second (high frequency)
```

---

## 📡 API Reference

### REST Endpoints

```bash
# Connection
POST /api/connect              {"testnet": true}
POST /api/disconnect
GET  /api/status              → {connected, streaming, price, bid, ask}

# Data
GET  /api/instruments/<asset>/<kind>  → ["BTC-PERPETUAL", ...]
GET  /api/chart-data          → [{time, open, high, low, close, regime}]
GET  /api/price-history       → [{time, price}]

# Streaming
POST /api/subscribe           {"symbol": "BTC-PERPETUAL"}
POST /api/unsubscribe         {"symbol": "BTC-PERPETUAL"}
```

### WebSocket Events

```javascript
// Connect to: ws://localhost:5000/socket.io/?transport=websocket

// Events from server to client:
socket.on('connection_status', {status, message})
socket.on('subscription_status', {status, symbol})
socket.on('price_update', {price, bid, ask, timestamp})

// Emit from client:
socket.emit('subscribe', {symbol})
```

---

## 🔍 Troubleshooting

### Problem: "No instruments found"
**Solution:** Check asset/type combination exists on Deribit
```bash
curl "https://test.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=future&expired=false"
```

### Problem: Connection timeout
**Solution:** Verify Deribit API is accessible
```bash
curl -I https://test.deribit.com/api/v2/public/get_instruments
# Should return HTTP 200
```

### Problem: High latency/lag
**Solution:** Reduce bar_duration or lower update frequency
```python
self.bar_duration = 1  # 1 second bars instead of 5
```

### Problem: Flask won't start (port in use)
**Solution:** Kill existing process or use different port
```bash
pkill -f "python3 app_flask"
# Or change port in app_flask.py:
# socketio.run(app, port=5001)
```

---

## 📚 Mathematical Details

### Gaussian Emission Probability

$$P(observation | state) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}$$

Where:
- μ (mu) = mean volatility for regime
- σ (sigma) = standard deviation
- x = observed volatility

### Viterbi Algorithm Recursion

$$V[s,t] = \max_s' \left( V[s',t-1] \times P(s|s') \times P(obs|s) \right)$$

Where:
- V = viterbi score (log-likelihood)
- s = current state
- s' = previous state
- P(s|s') = transition probability
- P(obs|s) = emission probability

---

## 🎓 Learning Path

1. **Basics** → Understand the 3 regimes (LOW/MEDIUM/HIGH)
2. **Calibration** → See how thresholds adapt to market data
3. **Viterbi** → Trace through algorithm step-by-step
4. **Trading** → Implement regime-based strategies
5. **Optimization** → Tune parameters for your markets

---

## 📝 Key Takeaways

✅ **Markov Model** automatically detects market regimes
✅ **HMM** finds optimal state sequence given observations
✅ **Viterbi Algorithm** guarantees best path
✅ **Transition Matrix** models regime persistence
✅ **Real-time Dashboard** shows regime changes instantly

---

## 🚀 Next Steps

1. **Paper Trade**: Test strategies on testnet
2. **Backtest**: Add historical data testing
3. **Add Signals**: Combine regime with technical indicators
4. **Connect Trading**: Execute trades based on regime changes
5. **Deploy**: Use gunicorn + systemd for production

---

**Need help?** Check the code comments or open a GitHub issue!
