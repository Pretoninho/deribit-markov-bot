import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime, timedelta
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import websocket
import json
import requests
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

class OHLCBar:
    def __init__(self, timestamp, open_price):
        self.timestamp = timestamp
        self.open = open_price
        self.high = open_price
        self.low = open_price
        self.close = open_price
        self.tick_count = 1
        self.regime = 0
    
    def update(self, price):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.tick_count += 1

    @property
    def volatility(self):
        return (self.high - self.low) / self.close if self.close > 0 else 0

class MarkovRegime:
    def __init__(self):
        pass
    
    def calibrate(self, hist_bars):
        pass
    
    def _gaussian_likelihood(self, vol, regime):
        pass
    
    def get_regime(self, bars):
        pass

class DeribitApp:
    def __init__(self, callback=None, testnet=True):
        self.callback = callback
        self.connected = False
        self.testnet = testnet
        self.base_url = "https://test.deribit.com/api/v2" if testnet else "https://www.deribit.com/api/v2"
        self.ws_url = "wss://test.deribit.com/ws/api/v2" if testnet else "wss://www.deribit.com/ws/api/v2"
        self.ws = None
        self.ws_thread = None
        self.running = False
        self.last_price = None
        self.bid_price = None
        self.ask_price = None
        self.historical_data = {}
        self.hist_done = threading.Event()
        self.current_symbol = None

    def connect(self):
        try:
            self.running = True
            self.ws_thread = threading.Thread(target=self._ws_connect, daemon=True)
            self.ws_thread.start()
            for i in range(50):
                if self.connected:
                    print(f"✓ Connecté à Deribit {'testnet' if self.testnet else 'mainnet'}")
                    return True
                time.sleep(0.1)
            print("✗ Erreur: Connexion WebSocket timeout")
            return False
        except Exception as e:
            print(f"✗ Erreur de connexion: {e}")
            return False

    def _ws_connect(self):
        try:
            self.ws = websocket.WebSocketApp(self.ws_url, on_open=self._on_ws_open, on_message=self._on_ws_message,
                                             on_error=self._on_ws_error, on_close=self._on_ws_close)
            self.ws.run_forever()
        except Exception as e:
            print(f"✗ Erreur WebSocket: {e}")
            self.connected = False

    def _on_ws_open(self, ws):
        self.connected = True
        print("WebSocket ouvert")

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'result' in data and data['result'] is None:
                return
            if 'params' in data and 'data' in data['params']:
                ticker_data = data['params']['data']
                price = ticker_data.get('last_price')
                bid = ticker_data.get('best_bid_price')
                ask = ticker_data.get('best_ask_price')
                if price and price > 0:
                    self.last_price = price
                    self.bid_price = bid or price
                    self.ask_price = ask or price
                    if self.callback:
                        self.callback('price', price, datetime.now())
        except Exception as e:
            print(f"✗ Erreur traitement message: {e}")

    def _on_ws_error(self, ws, error):
        print(f"✗ Erreur WebSocket: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        self.connected = False
        print("WebSocket fermé")

    def subscribe_ticker(self, symbol):
        if not self.connected:
            print("✗ Non connecté")
            return
        try:
            self.current_symbol = symbol
            subscribe_msg = {"jsonrpc": "2.0", "method": "public/subscribe", "id": 1,
                             "params": {"channels": [f"ticker.{symbol}.raw"]}}
            self.ws.send(json.dumps(subscribe_msg))
            print(f"✓ Abonné à {symbol}")
        except Exception as e:
            print(f"✗ Erreur abonnement: {e}")

    def unsubscribe_ticker(self, symbol):
        if not self.connected or not self.ws:
            return
        try:
            unsubscribe_msg = {"jsonrpc": "2.0", "method": "public/unsubscribe", "id": 1,
                               "params": {"channels": [f"ticker.{symbol}.raw"]}}
            self.ws.send(json.dumps(unsubscribe_msg))
        except Exception as e:
            print(f"✗ Erreur désabonnement: {e}")

    def get_historical_data(self, symbol, timeframe="5"):
        try:
            self.historical_data = {}
            params = {"instrument_name": symbol,
                      "start_timestamp": int((datetime.now() - timedelta(seconds=300)).timestamp() * 1000),
                      "end_timestamp": int(datetime.now().timestamp() * 1000),
                      "resolution": timeframe}
            response = requests.get(f"{self.base_url}/public/get_tradingview_chart_data", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    bars = data['result']
                    self.historical_data[symbol] = [{'o': bar.get('open'), 'h': bar.get('high'), 'l': bar.get('low'), 'c': bar.get('close')} for bar in bars]
                    print(f"✓ Données historiques chargées: {len(self.historical_data[symbol])} barres")
            self.hist_done.set()
        except Exception as e:
            print(f"✗ Erreur récupération données: {e}")
            self.hist_done.set()

    def get_instruments(self, currency, kind):
        try:
            params = {"currency": currency, "kind": kind, "expired": False}
            response = requests.get(f"{self.base_url}/public/get_instruments", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    return [inst['instrument_name'] for inst in data['result']]
            return []
        except Exception as e:
            print(f"✗ Erreur récupération instruments: {e}")
            return []

    def disconnect(self):
        self.running = False
        if self.ws:
            self.ws.close()
            self.connected = False
        print("Déconnecté de Deribit")

class LiveMarketDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title('Live Market Data Dashboard - Deribit')
        self.root.geometry('1400x900')
        self.root.configure(bg='#0d1117')
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_dark_theme()
        self.deribit_app = DeribitApp(callback=self.on_tick_data, testnet=True)
        self.connected = False
        self.streaming = False
        self.bar_duration = 5
        self.max_bars = 10
        self.ohlc_bars = deque(maxlen=self.max_bars)
        self.current_bar = None
        self.bar_start_time = None
        self.price_history = deque(maxlen=100)
        self.regime_model = MarkovRegime()
        self.bar_lock = threading.Lock()
        self.update_thread = None
        self.running = False
        self.setup_ui()
        self.setup_chart()
        self.load_instruments()

    def configure_dark_theme(self):
        bg_color = '#0d1117'
        fg_color = '#c9d1d9'
        entry_bg = '#161b22'
        self.style.configure('TFrame', background=bg_color)
        self.style.configure('TLabelframe', background=bg_color, foreground=fg_color)
        self.style.configure('TLabelframe.Label', background=bg_color, foreground=fg_color, font=('Segoe UI', 10, 'bold'))
        self.style.configure('TLabel', background=bg_color, foreground=fg_color, font=('Segoe UI', 10))
        self.style.configure('TButton', background=bg_color, foreground=fg_color, font=('Segoe UI', 9, 'bold'), padding=(10, 5))
        self.style.map('TButton', background=[('active', '#2ea043'), ('disabled', '#21262d')])
        self.style.configure('TEntry', fieldbackground=entry_bg, foreground=fg_color, insertcolor=fg_color)
        self.style.configure('TCombobox', fieldbackground=entry_bg, foreground=fg_color)
        self.style.configure('Accent.TButton', background='#da3633', foreground='white')
        self.style.map('Accent.TButton', background=[('active', '#f85149'), ('disabled', '#21262d')])

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding='15')
        main_frame.grid(row=0, column=0, sticky='nsew')
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky='ew', pady=(0, 15))
        title_label = tk.Label(header_frame, text="Deribit Regime Switching Bot", font=('JetBrains Mono', 18, 'bold'), bg='#0d1117', fg='#58a6ff')
        title_label.pack(side='left')
        self.status_indicator = tk.Label(header_frame, text='DISCONNECTED', font=('Segoe UI', 10, 'bold'), bg='#0d1117', fg='#f85149')
        self.status_indicator.pack(side='right', padx=10)
        control_frame = ttk.LabelFrame(main_frame, text='Control Panel', padding='10')
        control_frame.grid(row=1, column=0, sticky='ew', pady=(0, 15))
        conn_section = ttk.Frame(control_frame)
        conn_section.pack(fill='x', pady=(0, 10))
        ttk.Label(conn_section, text="Environment:").pack(side='left', padx=(0, 5))
        self.env_var = tk.StringVar(value='testnet')
        env_combo = ttk.Combobox(conn_section, textvariable=self.env_var, values=['testnet', 'mainnet'], width=10, state='readonly')
        env_combo.pack(side='left', padx=(0, 15))
        self.connect_btn = ttk.Button(conn_section, text="Connect", command=self.connect_deribit)
        self.connect_btn.pack(side='left', padx=(0, 5))
        self.disconnect_btn = ttk.Button(conn_section, text="Disconnect", command=self.disconnect_deribit, state='disabled', style='Accent.TButton')
        self.disconnect_btn.pack(side='left')
        sep = ttk.Separator(control_frame, orient='horizontal')
        sep.pack(fill='x', pady=10)
        data_section = ttk.Frame(control_frame)
        data_section.pack(fill='x')
        ttk.Label(data_section, text='Asset:').pack(side='left', padx=(0, 5))
        self.asset_var = tk.StringVar(value='BTC')
        asset_combo = ttk.Combobox(data_section, textvariable=self.asset_var, values=['BTC', 'ETH'], width=5, state='readonly')
        asset_combo.pack(side='left', padx=(0, 15))
        asset_combo.bind('<<ComboboxSelected>>', lambda e: self.load_instruments())
        ttk.Label(data_section, text='Type:').pack(side='left', padx=(0, 5))
        self.type_var = tk.StringVar(value='future')
        type_combo = ttk.Combobox(data_section, textvariable=self.type_var, values=['future', 'option'], width=8, state='readonly')
        type_combo.pack(side='left', padx=(0, 15))
        type_combo.bind('<<ComboboxSelected>>', lambda e: self.load_instruments())
        ttk.Label(data_section, text='Instrument:').pack(side='left', padx=(0, 5))
        self.symbol_var = tk.StringVar(value='BTC-PERPETUAL')
        self.symbol_combo = ttk.Combobox(data_section, textvariable=self.symbol_var, width=25, state='readonly')
        self.symbol_combo.pack(side='left', padx=(0, 5))
        self.stream_btn = ttk.Button(data_section, text="Start Stream", command=self.toggle_stream, state='disabled')
        self.stream_btn.pack(side='left', padx=(0, 5))
        self.recal_btn = ttk.Button(data_section, text="Recalibrate", command=self.recalibrate_model, state='disabled')
        self.recal_btn.pack(side='left', padx=(0, 15))
        price_frame = ttk.Frame(data_section)
        price_frame.pack(side='right')
        ttk.Label(price_frame, text="Last Price:", font=('Segoe UI', 10)).pack(side='left', padx=(0, 5))
        self.price_label = tk.Label(price_frame, text='---.--', font=('JetBrains Mono', 16, 'bold'), bg='#0d1117', fg='#7ee787')
        self.price_label.pack(side='left')
        chart_frame = ttk.LabelFrame(main_frame, text='Live OHLC with Markov Regime (5s Bars)', padding='10')
        chart_frame.grid(row=2, column=0, sticky='nsew')
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(0, weight=1)
        self.chart_container = ttk.Frame(chart_frame)
        self.chart_container.grid(row=0, column=0, sticky='nsew')
        self.chart_container.columnconfigure(0, weight=1)
        self.chart_container.rowconfigure(0, weight=1)
        stats_frame = ttk.Frame(main_frame)
        stats_frame.grid(row=3, column=0, sticky='ew', pady=(10, 0))
        self.stats_labels = {}
        stats = [('Bars', '0'), ('High', '--'), ('Low', '--'), ('Regime', '--'), ('Ticks/Bar', '0')]
        for i, (name, val) in enumerate(stats):
            frame = ttk.Frame(stats_frame)
            frame.pack(side='left', padx=15)
            ttk.Label(frame, text=f'{name}:', font=('Segoe UI', 9)).pack(side='left')
            label = tk.Label(frame, text=val, font=('JetBrains Mono', 10, 'bold'), bg='#0d1117', fg='#8b949e')
            label.pack(side='left', padx=(5, 0))
            self.stats_labels[name] = label

    def setup_chart(self):
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(14, 6), facecolor='#0d1117')
        self.ax.set_facecolor('#161b22')
        self.ax.tick_params(colors='#8b949e', labelsize=9)
        self.ax.spines['bottom'].set_color('#30363d')
        self.ax.spines['top'].set_color('#30363d')
        self.ax.spines['left'].set_color('#30363d')
        self.ax.spines['right'].set_color('#30363d')
        self.ax.grid(True, alpha=.2, color='#30363d', linestyle='--')
        self.ax.set_xlabel('Time', color='#8b949e', fontsize=10)
        self.ax.set_ylabel('Price', color='#8b949e', fontsize=10)
        self.ax.set_title('Waiting for data. . .', color='#c9d1d9', fontsize=12, fontweight='bold')
        self.canvas = FigureCanvasTkAgg(self.fig, self.chart_container)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
        self.fig.tight_layout()
        self.canvas.draw()

    def load_instruments(self):
        if not self.connected:
            return
        threading.Thread(target=self._load_instruments_async, daemon=True).start()

    def _load_instruments_async(self):
        try:
            asset = self.asset_var.get()
            kind = self.type_var.get()
            instruments = self.deribit_app.get_instruments(asset, kind)
            if instruments:
                self.symbol_combo['values'] = instruments
                if instruments:
                    self.symbol_var.set(instruments[0])
                print(f"✓ {len(instruments)} instruments chargés")
            else:
                print("✗ Aucun instrument trouvé")
        except Exception as e:
            print(f"✗ Erreur chargement instruments: {e}")

    def connect_deribit(self):
        try:
            testnet = self.env_var.get() == 'testnet'
            self.deribit_app.testnet = testnet
            if self.deribit_app.connect():
                self.connected = True
                self.connect_btn.config(state='disabled')
                self.disconnect_btn.config(state='normal')
                self.stream_btn.config(state='normal')
                self.status_indicator.config(text='CONNECTED', fg='#7ee787')
                self.load_instruments()
            else:
                messagebox.showerror('Error', 'Impossible de se connecter à Deribit')
        except Exception as e:
            messagebox.showerror('Error', f"Erreur connexion: {e}")

    def disconnect_deribit(self):
        try:
            if self.streaming:
                self.stop_stream()
            self.deribit_app.disconnect()
            self.connected = False
            self.connect_btn.config(state='normal')
            self.disconnect_btn.config(state='disabled')
            self.stream_btn.config(state='disabled')
            self.status_indicator.config(text='DISCONNECTED', fg='#f85149')
        except Exception as e:
            print(f"Erreur déconnexion: {e}")

    def toggle_stream(self):
        if not self.streaming:
            self.start_stream()
        else:
            self.stop_stream()

    def start_stream(self):
        if not self.connected:
            return
        symbol = self.symbol_var.get()
        if not symbol:
            messagebox.showerror('Error', 'Veuillez sélectionner un instrument')
            return
        with self.bar_lock:
            self.ohlc_bars.clear()
            self.current_bar = None
            self.bar_start_time = None
            self.price_history.clear()
            self.regime_model = MarkovRegime()
        self.deribit_app.historical_data.clear()
        self.deribit_app.hist_done.clear()
        hist_thread = threading.Thread(target=self.deribit_app.get_historical_data, args=(symbol,), daemon=True)
        hist_thread.start()
        if self.deribit_app.hist_done.wait(timeout=10):
            if symbol in self.deribit_app.historical_data:
                self.regime_model.calibrate(self.deribit_app.historical_data[symbol])
                print(f"✓ Modèle calibré avec {len(self.deribit_app.historical_data[symbol])} barres")
        self.deribit_app.subscribe_ticker(symbol)
        self.streaming = True
        self.running = True
        self.stream_btn.config(text='Stop Stream', style='Accent.TButton')
        self.recal_btn.config(state='normal')
        self.status_indicator.config(text=f'Streaming {symbol}', fg='#58a6ff')
        self.update_thread = threading.Thread(target=self.bar_manager_loop, daemon=True)
        self.update_thread.start()
        self.update_chart_loop()

    def stop_stream(self):
        self.running = False
        self.streaming = False
        try:
            if self.deribit_app.current_symbol:
                self.deribit_app.unsubscribe_ticker(self.deribit_app.current_symbol)
        except Exception as e:
            print(f"Erreur désabonnement: {e}")
        self.stream_btn.config(text='Start Stream', style='TButton')
        self.recal_btn.config(state='disabled')
        self.status_indicator.config(text="CONNECTED", fg='#7ee787')

    def recalibrate_model(self):
        pass

    def on_tick_data(self, data_type, value, timestamp):
        if data_type == 'price' and value > 0:
            with self.bar_lock:
                self.price_history.append((timestamp, value))
                if self.current_bar is None:
                    self.current_bar = OHLCBar(timestamp, value)
                    self.bar_start_time = timestamp
                else:
                    self.current_bar.update(value)
                self.root.after(0, lambda: self.price_label.config(text=f'{value:.2f}'))

    def bar_manager_loop(self):
        while self.running:
            time.sleep(0.1)
            with self.bar_lock:
                if self.current_bar is not None and self.bar_start_time is not None:
                    elapsed = (datetime.now() - self.bar_start_time).total_seconds()
                    if elapsed >= self.bar_duration:
                        self.ohlc_bars.append(self.current_bar)
                        self.regime_model.get_regime(list(self.ohlc_bars))
                        last_price = self.current_bar.close
                        self.current_bar = OHLCBar(datetime.now(), last_price)
                        self.bar_start_time = datetime.now()

    def update_chart_loop(self):
        if not self.running:
            return
        self.draw_ohlc_chart()
        self.update_stats()
        self._after_id = self.root.after(200, self.update_chart_loop)

    def draw_ohlc_chart(self):
        self.ax.clear()
        with self.bar_lock:
            bars = list(self.ohlc_bars)
            current = self.current_bar
            if current is not None:
                bars = bars + [current]
            if not bars:
                self.ax.set_facecolor('#161b22')
                self.ax.set_title('Waiting for data. . .', color='#c9d1d9', fontsize=12, fontweight='bold')
                self.ax.grid(True, alpha=.2, color='#30363d', linestyle='--')
                self.canvas.draw_idle()
                return
            all_prices = [bar.low for bar in bars] + [bar.high for bar in bars]
            price_min, price_max = min(all_prices), max(all_prices)
            price_range = price_max - price_min
            padding = max(price_range * .1, .01)
            y_min, y_max = price_min - padding, price_max + padding
            width = 0.6
            for i, bar in enumerate(bars):
                color, edge_color = ('#3fb950', '#7ee787') if bar.close >= bar.open else ('#f85149', '#ff7b72')
                body_bottom, body_height = min(bar.open, bar.close), max(abs(bar.close - bar.open), .001)
                rect = Rectangle((i - width/2, body_bottom), width, body_height, facecolor=color, edgecolor=edge_color, linewidth=1.5, alpha=.9, zorder=2)
                self.ax.add_patch(rect)
                self.ax.plot([i, i], [bar.low, body_bottom], color=edge_color, linewidth=1.5, zorder=1)
                self.ax.plot([i, i], [body_bottom + body_height, bar.high], color=edge_color, linewidth=1.5, zorder=1)
                if i == len(bars) - 1 and current is not None:
                    self.ax.axvline(x=i, color='#58a6ff', alpha=.3, linestyle=':', linewidth=2)
            self.ax.set_facecolor('#161b22')
            x_labels = [bar.timestamp.strftime('%H:%M:%S') for bar in bars]
            self.ax.set_xticks(range(len(bars)))
            self.ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
            self.ax.set_ylim(y_min, y_max)
            self.ax.set_xlim(-.5, max(self.max_bars - .5, len(bars) - .5))
            self.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.3f}'))
            symbol = self.symbol_var.get()
            regime_names = ['LOW', 'MED', 'HIGH']
            curr_regime = regime_names[bars[-1].regime] if bars else 'N/A'
            self.ax.set_title(f'{symbol} - Regime: {curr_regime} | {len(bars)}/{self.max_bars} bars', color='#c9d1d9', fontsize=12, fontweight='bold')
            self.fig.tight_layout()
            self.canvas.draw_idle()

    def update_stats(self):
        with self.bar_lock:
            bars = list(self.ohlc_bars)
            current = self.current_bar
            if current:
                bars = bars + [current]
            if not bars:
                return
            self.stats_labels['Bars'].config(text=str(len(bars)))
            all_highs = [b.high for b in bars]
            all_lows = [b.low for b in bars]
            self.stats_labels['High'].config(text=f'{max(all_highs):.2f}')
            self.stats_labels['Low'].config(text=f'{min(all_lows):.2f}')
            regime_names = ['LOW', 'MED', 'HIGH']
            regime_colors = ['#3fb950', '#d29922', '#f85149']
            curr_regime = bars[-1].regime if bars else 0
            self.stats_labels['Regime'].config(text=regime_names[curr_regime], fg=regime_colors[curr_regime])
            if current:
                self.stats_labels['Ticks/Bar'].config(text=str(current.tick_count))

    def on_closing(self):
        self.running = False
        if hasattr(self, '_after_id'):
            self.root.after_cancel(self._after_id)
        if self.connected:
            try:
                if self.streaming:
                    self.stop_stream()
                self.deribit_app.disconnect()
            except Exception as e:
                print(f"Erreur fermeture: {e}")
        self.root.destroy()

def main():
    root = tk.Tk()
    app = LiveMarketDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()