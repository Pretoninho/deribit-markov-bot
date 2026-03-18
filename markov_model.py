"""
Markov Regime Detection using Hidden Markov Model (HMM)
Detects volatility regimes: LOW, MEDIUM, HIGH
"""
import numpy as np
from datetime import datetime
from scipy import stats

class OHLCBar:
    """OHLC Bar representation"""
    def __init__(self, timestamp, open_price):
        self.timestamp = timestamp
        self.open = open_price
        self.high = open_price
        self.low = open_price
        self.close = open_price
        self.tick_count = 1
        self.regime = 0  # 0=LOW, 1=MEDIUM, 2=HIGH
    
    def update(self, price):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.tick_count += 1
    
    @property
    def volatility(self):
        """Intra-bar volatility = (high-low)/close"""
        return (self.high - self.low) / self.close if self.close > 0 else 0
    
    @property
    def direction(self):
        """Price direction: 1=up, -1=down"""
        return 1 if self.close >= self.open else -1
    
    @property
    def amplitude(self):
        """Absolute price movement"""
        return abs(self.close - self.open)


class MarkovRegime:
    """
    Hidden Markov Model for volatility regime detection
    
    States:
    - State 0 (LOW): Low volatility, mean-reverting
    - State 1 (MEDIUM): Medium volatility, trending
    - State 2 (HIGH): High volatility, trending/volatile
    """
    
    def __init__(self, n_states=3):
        self.n_states = n_states
        
        # Transition matrix: P(state_t | state_t-1)
        self.transition_matrix = np.array([
            [0.70, 0.20, 0.10],  # From LOW
            [0.25, 0.60, 0.15],  # From MEDIUM
            [0.10, 0.25, 0.65]   # From HIGH
        ])
        
        # Emission parameters (volatility thresholds)
        # LOW: vol < 0.5%, MEDIUM: 0.5% <= vol < 1.5%, HIGH: vol >= 1.5%
        self.vol_thresholds = [0.005, 0.015]
        
        # Initial state distribution
        self.initial_probs = np.array([0.60, 0.30, 0.10])
        
        # Regime characteristics (trained from data)
        self.regime_params = None
        self.current_state = 0
        self.min_bars_for_training = 20
    
    def calibrate(self, bars_data):
        """
        Calibrate the HMM with historical data
        
        Args:
            bars_data: List of bar dictionaries with 'o', 'h', 'l', 'c' keys
        """
        if not bars_data or len(bars_data) < self.min_bars_for_training:
            return
        
        # Extract volatilities
        vols = []
        for bar in bars_data:
            vol = (bar.get('h', 0) - bar.get('l', 0)) / bar.get('c', 1) if bar.get('c', 0) > 0 else 0
            vols.append(vol)
        
        vols = np.array(vols)
        
        # Calculate percentiles for dynamic threshold setting
        p25 = np.percentile(vols, 25)
        p75 = np.percentile(vols, 75)
        
        # Update thresholds based on data
        self.vol_thresholds = [p25, p75]
        
        print(f"✓ Model calibrated with {len(bars_data)} bars")
        print(f"  Volatility thresholds: LOW={p25:.4f}, HIGH={p75:.4f}")
    
    def _emit_probability(self, volatility, state):
        """
        Calculate emission probability P(observation | state)
        Using Gaussian distribution
        """
        # Define regime volatility characteristics
        regime_means = [0.003, 0.008, 0.020]  # Expected volatility per state
        regime_stds = [0.001, 0.003, 0.010]   # Std dev per state
        
        mean = regime_means[state]
        std = regime_stds[state]
        
        # Gaussian probability density
        if std > 0:
            prob = stats.norm.pdf(volatility, mean, std)
        else:
            prob = 1.0 if volatility == mean else 0.0
        
        return max(prob, 1e-10)  # Avoid zero
    
    def _viterbi_algorithm(self, observations):
        """
        Viterbi algorithm for finding most likely state sequence
        
        Args:
            observations: List of volatilities
        
        Returns:
            List of most likely states
        """
        n_obs = len(observations)
        
        # Initialize
        viterbi = np.zeros((self.n_states, n_obs))
        backpointer = np.zeros((self.n_states, n_obs), dtype=int)
        
        # Initialization step
        for state in range(self.n_states):
            emit_prob = self._emit_probability(observations[0], state)
            viterbi[state, 0] = np.log(self.initial_probs[state]) + np.log(emit_prob)
        
        # Recursion step
        for t in range(1, n_obs):
            for state in range(self.n_states):
                emit_prob = self._emit_probability(observations[t], state)
                
                # Find max transition from any previous state
                prev_states = viterbi[:, t-1] + np.log(self.transition_matrix[:, state])
                best_prev_state = np.argmax(prev_states)
                
                viterbi[state, t] = prev_states[best_prev_state] + np.log(emit_prob)
                backpointer[state, t] = best_prev_state
        
        # Backtrack to find path
        states = np.zeros(n_obs, dtype=int)
        states[-1] = np.argmax(viterbi[:, -1])
        
        for t in range(n_obs - 2, -1, -1):
            states[t] = backpointer[states[t + 1], t + 1]
        
        return states.tolist()
    
    def get_regime(self, bars):
        """
        Detect current regime from recent bars
        
        Args:
            bars: List of OHLCBar objects
        
        Returns:
            Current regime (0=LOW, 1=MEDIUM, 2=HIGH)
        """
        if not bars or len(bars) < 2:
            return self.current_state
        
        # Extract volatilities from bars
        volatilities = [bar.volatility for bar in bars]
        
        # For very recent data, use simple thresholding
        if len(bars) < 5:
            current_vol = volatilities[-1]
            if current_vol < self.vol_thresholds[0]:
                self.current_state = 0
            elif current_vol < self.vol_thresholds[1]:
                self.current_state = 1
            else:
                self.current_state = 2
        else:
            # Use Viterbi for longer sequences
            states = self._viterbi_algorithm(volatilities)
            self.current_state = states[-1] if states else self.current_state
        
        # Clamp to valid state
        self.current_state = max(0, min(2, self.current_state))
        
        return self.current_state
    
    def get_regime_name(self, regime):
        """Get human-readable regime name"""
        names = ["LOW", "MEDIUM", "HIGH"]
        return names[max(0, min(2, regime))]
    
    def get_regime_confidence(self, bars):
        """
        Calculate confidence in the current regime prediction
        
        Returns:
            Float 0-1 indicating confidence
        """
        if not bars or len(bars) < 2:
            return 0.5
        
        volatilities = np.array([bar.volatility for bar in bars[-10:]])
        
        if len(volatilities) == 0:
            return 0.5
        
        # Higher concentration = higher confidence
        cv = np.std(volatilities) / (np.mean(volatilities) + 1e-6)  # Coefficient of variation
        confidence = np.exp(-cv)  # Exponential decay
        
        return max(0.0, min(1.0, confidence))
    
    def predict_next_regime(self, current_regime):
        """
        Predict next regime using transition matrix
        
        Returns:
            Tuple of (most_likely_regime, probability)
        """
        probs = self.transition_matrix[current_regime]
        next_regime = np.argmax(probs)
        probability = probs[next_regime]
        
        return next_regime, probability
