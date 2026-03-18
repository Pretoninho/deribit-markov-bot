# Deribit Markov Chain Regime Switching Bot

## Overview
Adaptation of the Interactive Brokers Markov Chain Regime Switching Bot to use **Deribit** API for market data feeds.

## Features

✅ **Public API Only** - No authentication needed for market data retrieval
✅ **Futures & Options Support** - Trade both BTC and ETH derivatives
✅ **Real-time WebSocket** - Live price feeds via Deribit WebSocket API
✅ **Historical Data** - 5-second OHLC bars from REST API
✅ **Testnet/Mainnet** - Toggle between environments
✅ **Dark Theme UI** - Professional trading interface

## Supported Symbols

### Futures
- `BTC-PERPETUAL` - Bitcoin perpetual contract
- `ETH-PERPETUAL` - Ethereum perpetual contract
- `BTC-27JUN25` - Bitcoin futures dated June 27, 2025
- `ETH-27JUN25` - Ethereum futures dated June 27, 2025

### Options
- `BTC-27JUN25-50000-C` - BTC Call 50000 strike
- `BTC-27JUN25-50000-P` - BTC Put 50000 strike
- `ETH-27JUN25-3500-C` - ETH Call 3500 strike
- `ETH-27JUN25-3500-P` - ETH Put 3500 strike

## Installation

```bash
# Install dependencies
pip install -r requirements_deribit.txt

# Or manually:
pip install websocket-client requests matplotlib# deribit-markov-bot
Bot Markov Chain Regime Switching pour utiliser Deribit
