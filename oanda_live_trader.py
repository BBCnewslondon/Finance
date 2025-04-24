import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.positions as positions
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

OANDA_API_KEY = os.getenv("OANDA_API_KEY")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT")


# Strategy Parameters (from your latest successful WF OOS run, e.g., row 1)
# These need to be updated based on periodic re-optimization
STRATEGY_PARAMS = {
    'pair': "EUR_USD", # OANDA uses underscores
    'instrument': "EUR_USD",
    'granularity': "H1", # OANDA granularity (e.g., 'M1', 'H1', 'D') - CHOOSE ONE CONSISTENTLY
    'cooldown_periods': 10, # Number of bars for cooldown
    'lookback_period': 17,
    'use_atr_filter': False,
    'atr_period': None, # Set based on params if use_atr_filter is True
    'atr_ma_period': None, # Set based on params if use_atr_filter is True
    'use_adx_filter': False,
    'adx_period': 14, # Set based on params if use_adx_filter is True
    'adx_trend_threshold': None, # Set based on params if use_adx_filter is True
    'use_adx_whipsaw_filter': True,
    'adx_whipsaw_threshold': 12.0,
    'use_adaptive_rr': False,
    'base_rr': None, # Set based on params if use_adaptive_rr is True
    'atr_multiplier_rr': None, # Set based on params if use_adaptive_rr is True
    'fixed_rr': 2.0, # Assuming fixed RR based on your example's rr_ratio=2.0 when use_adaptive_rr=False
    'stop_loss_pips': 50, # EXAMPLE: Define how SL is set (pips, ATR, etc.) - NEEDS LOGIC
    'take_profit_pips': 100, # EXAMPLE: Define how TP is set (pips, ATR, R:R) - NEEDS LOGIC
    'trade_units': 1000 # Example trade size
}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("trading_log.log"), logging.StreamHandler()])


try:
    api = oandapyV20.API(access_token=OANDA_API_KEY, environment=OANDA_ENVIRONMENT)
    logging.info("Successfully connected to OANDA API.")
except Exception as e:
    logging.error(f"Failed to connect to OANDA API: {e}")
    exit()

# --- Global State ---
last_trade_exit_time = None
cooldown_active = False

# --- Indicator Calculation Functions ---

def calculate_atr(df, period=14):
    """Calculates Average True Range."""
    # --- Adapt ATR calculation logic from finance.ipynb ---
    # Example placeholder:
    if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
        logging.warning("Missing HLC columns for ATR calculation.")
        return df
    # ... (Your ATR calculation logic using high, low, close) ...
    # df['tr'] = ...
    # df['atr'] = df['tr'].rolling(window=period).mean()
    logging.info("ATR calculation needs to be implemented.") # Placeholder message
    df['atr'] = 0.0 # Placeholder
    return df

def calculate_adx(df, period=14):
    """Calculates Average Directional Index (ADX)."""
    # --- Adapt ADX calculation logic from finance.ipynb ---
    # Example placeholder:
    if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
        logging.warning("Missing HLC columns for ADX calculation.")
        return df
    # ... (Your ADX, +DI, -DI calculation logic) ...
    logging.info("ADX calculation needs to be implemented.") # Placeholder message
    df['adx'] = 25.0 # Placeholder
    df['plus_di'] = 20.0 # Placeholder
    df['minus_di'] = 20.0 # Placeholder
    return df

def calculate_signals(df, params):
    """Calculates entry/exit signals based on strategy logic."""
    # --- Adapt signal generation logic from finance.ipynb ---
    # This needs to replicate the core logic of run_derivative_backtest_for_pair_with_cooldown
    # including derivative calculation, filter checks, and entry conditions.
    # It should add 'signal' (1 for long, -1 for short, 0 for none) column.

    logging.info("Signal calculation needs to be implemented.") # Placeholder message
    df['signal'] = 0 # Placeholder: No signal
    # Example: Add a dummy signal on the last row for testing
    # df.loc[df.index[-1], 'signal'] = 1 # Dummy long signal

    return df

# --- OANDA Interaction Functions ---

def get_latest_candles(instrument, count, granularity):
    """Fetches the latest candles from OANDA."""
    params = {"count": count, "granularity": granularity}
    try:
        r = instruments.InstrumentsCandles(instrument=instrument, params=params)
        api.request(r)
        data = r.response.get('candles')
        if not data:
            logging.warning(f"No candle data received for {instrument}")
            return None

        records = []
        for candle in data:
            time_val = pd.to_datetime(candle.get('time'))
            volume = candle.get('volume')
            complete = candle.get('complete')
            if complete and 'mid' in candle: # Use 'mid' prices, or 'bidask' if needed
                rec = {
                    'time': time_val,
                    'open': float(candle['mid']['o']),
                    'high': float(candle['mid']['h']),
                    'low': float(candle['mid']['l']),
                    'close': float(candle['mid']['c']),
                    'volume': volume
                }
                records.append(rec)

        df = pd.DataFrame(records)
        df.set_index('time', inplace=True)
        return df

    except oandapyV20.exceptions.V20Error as e:
        logging.error(f"OANDA API Error fetching candles: {e}")
    except Exception as e:
        logging.error(f"Error fetching candles: {e}")
    return None

def get_open_trades():
    """Gets a list of open trades for the account."""
    try:
        r = trades.OpenTrades(accountID=OANDA_ACCOUNT_ID)
        api.request(r)
        return r.response.get('trades', [])
    except oandapyV20.exceptions.V20Error as e:
        logging.error(f"OANDA API Error fetching open trades: {e}")
    except Exception as e:
        logging.error(f"Error fetching open trades: {e}")
    return []

def get_open_positions():
    """Gets open positions for the account."""
    try:
        r = positions.OpenPositions(accountID=OANDA_ACCOUNT_ID)
        api.request(r)
        return r.response.get('positions', [])
    except oandapyV20.exceptions.V20Error as e:
        logging.error(f"OANDA API Error fetching open positions: {e}")
    except Exception as e:
        logging.error(f"Error fetching open positions: {e}")
    return []

def place_order(instrument, units, stop_loss_pips, take_profit_pips):
    """Places a market order with SL and TP."""
    # --- Determine SL and TP prices ---
    # This is crucial and needs proper implementation based on current price
    # and whether it's a long or short trade (units > 0 or units < 0)
    # You'll need to fetch the current price.
    # For now, using fixed pips as an example.
    # A pip is typically 0.0001 for EURUSD.

    # Fetch current price to calculate SL/TP - requires another API call or use recent candle
    candles = get_latest_candles(instrument, 1, "S5") # Get 5-second candle for current price
    if candles is None or candles.empty:
        logging.error("Could not get current price to set SL/TP.")
        return None
    current_price = candles['close'].iloc[-1]
    pip_value = 0.0001 # Adjust for JPY pairs etc.

    if units > 0: # Long order
        sl_price = current_price - stop_loss_pips * pip_value
        tp_price = current_price + take_profit_pips * pip_value
    elif units < 0: # Short order
        sl_price = current_price + stop_loss_pips * pip_value
        tp_price = current_price - take_profit_pips * pip_value
    else:
        logging.warning("Attempted to place order with zero units.")
        return None

    order_data = {
        "order": {
            "instrument": instrument,
            "units": str(units), # Must be a string
            "type": "MARKET",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {
                "timeInForce": "GTC", # Good 'til Canceled
                "price": f"{sl_price:.5f}" # Format price to 5 decimal places for EURUSD
            },
            "takeProfitOnFill": {
                "timeInForce": "GTC",
                "price": f"{tp_price:.5f}"
            }
        }
    }

    try:
        r = orders.OrderCreate(accountID=OANDA_ACCOUNT_ID, data=order_data)
        api.request(r)
        logging.info(f"Order placement response: {r.response}")
        # Check 'orderFillTransaction' or 'orderCancelTransaction' in response
        if 'orderFillTransaction' in r.response:
             logging.info(f"Order filled for {units} units of {instrument}.")
             return r.response['orderFillTransaction']
        elif 'orderCancelTransaction' in r.response:
             logging.warning(f"Order canceled: {r.response['orderCancelTransaction'].get('reason')}")
             return None
        else:
             logging.warning(f"Order status unclear: {r.response}")
             return None # Or handle other transaction types

    except oandapyV20.exceptions.V20Error as e:
        logging.error(f"OANDA API Error placing order: {e}. Response: {e.body}")
    except Exception as e:
        logging.error(f"Error placing order: {e}")
    return None


# --- Main Trading Loop ---
def run_trader():
    global last_trade_exit_time, cooldown_active

    logging.info("Starting trading loop...")
    while True:
        try:
            # --- Cooldown Check ---
            if cooldown_active:
                # Calculate when cooldown ends (requires knowing candle duration)
                # This needs refinement based on granularity
                # Example for H1 granularity:
                cooldown_end_time = last_trade_exit_time + timedelta(hours=STRATEGY_PARAMS['cooldown_periods'])
                if datetime.utcnow() >= cooldown_end_time:
                    cooldown_active = False
                    last_trade_exit_time = None
                    logging.info("Cooldown finished.")
                else:
                    # Still in cooldown, wait before next check
                    logging.debug(f"Cooldown active until {cooldown_end_time}. Sleeping...")
                    time.sleep(60) # Check cooldown every minute
                    continue # Skip rest of the loop

            # --- Position Check ---
            # Check if we already have a position for the instrument
            open_positions = get_open_positions()
            instrument_position = None
            for pos in open_positions:
                if pos.get('instrument') == STRATEGY_PARAMS['instrument']:
                    instrument_position = pos
                    break

            if instrument_position:
                # We have an open position, managed by SL/TP orders.
                # Log status periodically or implement other management if needed.
                long_units = int(instrument_position.get('long', {}).get('units', 0))
                short_units = int(instrument_position.get('short', {}).get('units', 0))
                if long_units > 0:
                     logging.info(f"Holding LONG position: {long_units} units.")
                elif short_units < 0:
                     logging.info(f"Holding SHORT position: {short_units} units.")
                # No action needed here if SL/TP are set, OANDA handles exit.
                # If a trade closes, the position disappears. We need to detect this
                # transition to start the cooldown. This part is tricky and might
                # require checking trade history or position status changes.
                # For simplicity now, we assume SL/TP handles exits. Cooldown starts
                # when position is detected as closed (logic needs adding).

            else:
                # No open position for this instrument, check for entry signals
                logging.info(f"No open position for {STRATEGY_PARAMS['instrument']}. Checking for signals...")

                # --- Fetch Data & Calculate Indicators ---
                # Fetch enough data for lookback + indicator periods
                # e.g., lookback_period + max(atr_period, adx_period) + buffer
                num_candles_needed = STRATEGY_PARAMS['lookback_period'] + 50 # Adjust buffer as needed
                df = get_latest_candles(STRATEGY_PARAMS['instrument'],
                                        num_candles_needed,
                                        STRATEGY_PARAMS['granularity'])

                if df is None or len(df) < num_candles_needed - 10: # Allow some tolerance
                    logging.warning("Insufficient data received. Skipping signal check.")
                    time.sleep(30) # Wait before retrying data fetch
                    continue

                # --- Apply Indicators ---
                # IMPORTANT: Call your adapted indicator functions here
                # df = calculate_atr(df, STRATEGY_PARAMS['atr_period']) # If needed
                # df = calculate_adx(df, STRATEGY_PARAMS['adx_period']) # If needed
                df = calculate_signals(df, STRATEGY_PARAMS) # Your core signal logic

                # --- Check Signal on Latest Completed Candle ---
                latest_signal = df['signal'].iloc[-1] # Check the last row

                if latest_signal == 1: # Long Signal
                    logging.info(f"LONG signal detected for {STRATEGY_PARAMS['instrument']}.")
                    # Place Long Order
                    fill_info = place_order(STRATEGY_PARAMS['instrument'],
                                            STRATEGY_PARAMS['trade_units'], # Positive units for long
                                            STRATEGY_PARAMS['stop_loss_pips'],
                                            STRATEGY_PARAMS['take_profit_pips'])
                    if fill_info:
                         logging.info("Long order placed successfully.")
                         # Cooldown should start *after* this trade closes.
                         # Need logic to detect trade closure.

                elif latest_signal == -1: # Short Signal
                    logging.info(f"SHORT signal detected for {STRATEGY_PARAMS['instrument']}.")
                    # Place Short Order
                    fill_info = place_order(STRATEGY_PARAMS['instrument'],
                                            -STRATEGY_PARAMS['trade_units'], # Negative units for short
                                            STRATEGY_PARAMS['stop_loss_pips'],
                                            STRATEGY_PARAMS['take_profit_pips'])
                    if fill_info:
                         logging.info("Short order placed successfully.")
                         # Cooldown should start *after* this trade closes.

                else: # No Signal
                    logging.info("No entry signal detected.")


            # --- Wait before next check ---
            # Adjust sleep time based on granularity (e.g., 60s for M1, 3600s for H1)
            # Be mindful of API rate limits
            sleep_duration = 60 # Check every minute (adjust as needed)
            logging.debug(f"Sleeping for {sleep_duration} seconds...")
            time.sleep(sleep_duration)

        except KeyboardInterrupt:
            logging.info("Trader stopped manually.")
            break
        except Exception as e:
            logging.error(f"An error occurred in the main loop: {e}", exc_info=True)
            logging.info("Restarting loop after 60 seconds...")
            time.sleep(60) # Wait after an error before retrying


if __name__ == "__main__":
    run_trader()