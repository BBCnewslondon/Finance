import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.positions as positions
import pandas as pd
import time
import logging
from datetime import datetime, timedelta

class OandaTrader:
    def __init__(self, api, account_id=None, strategy_params=None, calculate_signals_function=None, indicator_functions=None, buffer=50):
        """
        Initialize the Oanda Trader

        Args:
            api: oandapyV20.API object for API connections
            account_id: OANDA account ID (defaults to env var)
            strategy_params: Dict of strategy parameters
            calculate_signals_function: Function to calculate trading signals
            indicator_functions: Dict of {name: function} for indicators
        """
        self.api = api
        self.account_id = account_id
        self.strategy_params = strategy_params
        self.calculate_signals = calculate_signals_function
        self.indicator_functions = indicator_functions

        # State variables
        self.last_trade_exit_time = None
        self.cooldown_active = False
        self.buffer = buffer
        self.candles_needed = self.strategy_params['lookback_period'] + self.buffer

        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{self.strategy_params['instrument']}_trader.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def apply_indicators(self, df):
        """Apply all registered indicator functions to the dataframe"""
        for indicator_name, function in self.indicator_functions.items():
            try:
                df = function(df, self.strategy_params)
                self.logger.info(f"Applied {indicator_name} indicator")
            except Exception as e:
                self.logger.error(f"Error calculating {indicator_name}: {e}")
        return df

    def get_latest_candles(self, instrument, count, granularity):
        """Fetches the latest candles from OANDA."""
        params = {"count": count, "granularity": granularity}
        try:
            r = instruments.InstrumentsCandles(instrument=instrument, params=params)
            self.api.request(r)
            data = r.response.get('candles')
            if not data:
                self.logger.warning(f"No candle data received for {instrument}")
                return None

            records = []
            for candle in data:
                time_val = pd.to_datetime(candle.get('time'))
                volume = candle.get('volume')
                complete = candle.get('complete')
                if complete and 'mid' in candle:
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
            if not df.empty:
                df.set_index('time', inplace=True)
            return df

        except Exception as e:
            self.logger.error(f"Error fetching candles: {e}")
            return None

    def get_open_trades(self):
        """Gets open trades for the account."""
        try:
            r = positions.OpenPositions(accountID=self.account_id)
            self.api.request(r)
            return r.response.get('trades', [])
        except Exception as e:
            self.logger.error(f"Error fetching open trades: {e}")
            return []

    def get_open_positions(self):
        """Gets open positions for the account."""
        try:
            r = positions.OpenPositions(accountID=self.account_id)
            self.api.request(r)
            return r.response.get('positions', [])
        except Exception as e:
            self.logger.error(f"Error fetching open positions: {e}")
            return []

    def place_order(self, instrument, units, stop_loss_pips, take_profit_pips):
        """Places a market order with SL and TP."""
        # Get current price
        candles = self.get_latest_candles(instrument, 1, "S5")
        if candles is None or candles.empty:
            self.logger.error("Could not get current price to set SL/TP")
            return None

        current_price = candles['close'].iloc[-1]
        pip_value = 0.0001  # For most currency pairs

        if units > 0:  # Long
            sl_price = current_price - stop_loss_pips * pip_value
            tp_price = current_price + take_profit_pips * pip_value
        elif units < 0:  # Short
            sl_price = current_price + stop_loss_pips * pip_value
            tp_price = current_price - take_profit_pips * pip_value
        else:
            self.logger.warning("Attempted to place order with zero units")
            return None

        order_data = {
            "order": {
                "instrument": instrument,
                "units": str(units),
                "type": "MARKET",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{sl_price:.5f}"
                },
                "takeProfitOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{tp_price:.5f}"
                }
            }
        }

        try:
            r = orders.OrderCreate(accountID=self.account_id, data=order_data)
            self.api.request(r)

            if 'orderFillTransaction' in r.response:
                self.logger.info(f"Order filled: {units} units of {instrument}") # Check 'orderFillTransaction' or 'orderCancelTransaction' in response
                return r.response['orderFillTransaction']
            elif 'orderCancelTransaction' in r.response:
                self.logger.warning(f"Order canceled: {r.response['orderCancelTransaction'].get('reason')}")
            else:
                self.logger.warning(f"Order status unclear: {r.response}")

            return None

        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None

    def run_trader(self, sleep_duration=60):
        self.logger.info("Starting trading loop...")

        while True:
            try:
                # Check if in cooldown
                if self.cooldown_active:
                    cooldown_end_time = self.last_trade_exit_time + timedelta(hours=self.strategy_params['cooldown_periods'])

                    if datetime.datetime.datetime.now(datetime.UTC) >= cooldown_end_time:
                        self.cooldown_active = False
                        self.last_trade_exit_time = None
                        self.logger.info("Cooldown finished")

                    else:
                        self.logger.info(f"Cooldown active until {cooldown_end_time}")
                        time.sleep(60)
                        continue

                # Check for existing position
                open_positions = self.get_open_positions()
                has_position = False

                for pos in open_positions:
                    if pos.get('instrument') == self.strategy_params['instrument']:
                        has_position = True
                        long_units = int(pos.get('long', {}).get('units', 0))
                        short_units = int(pos.get('short', {}).get('units', 0))

                        if long_units > 0:
                            self.logger.info(f"Holding LONG position: {long_units} units")
                        elif short_units < 0:
                            self.logger.info(f"Holding SHORT position: {short_units} units")
                        break

                # Check for new signals if no position
                if not has_position:
                    self.logger.info(f"No position for {self.strategy_params['instrument']}, checking signals")

                    # Extra candles for calculations
                    df = self.get_latest_candles(
                        self.strategy_params['instrument'],
                        self.candles_needed,
                        self.strategy_params['granularity']
                    )

                    if df is None or len(df) < self.candles_needed - 10:
                        self.logger.warning("Insufficient data received, skipping signal check.")
                        time.sleep(30)
                        continue

                    # Apply indicators and get signals
                    df = self.apply_indicators(df)
                    df = self.calculate_signals(df, self.strategy_params)

                    # Check latest signal
                    latest_signal = df['signal'].iloc[-1]

                    if latest_signal == 1:  # Long signal
                        self.logger.info(f"LONG signal detected for {self.strategy_params['instrument']}")
                        
                        # Extract the latest stop loss and take profit pips as scalar values
                        stop_loss_pips = float(df['stop_loss_pips'].iloc[-1])
                        take_profit_pips = float(df['take_profit_pips'].iloc[-1])

                        fill_info = self.place_order(
                            self.strategy_params['instrument'],
                            self.strategy_params['trade_units'],
                            stop_loss_pips,
                            take_profit_pips
                        )

                        if fill_info:
                            self.logger.info(f"LONG order filled: {fill_info}")
                            self.last_trade_exit_time = datetime.datetime.now(datetime.UTC)
                            self.cooldown_active = True
                            self.logger.info("Entering cooldown period after trade")
                            # TODO: Need to verify cooldown logic and detect trade closure

                    elif latest_signal == -1:  # Short signal
                        self.logger.info(f"SHORT signal for {self.strategy_params['instrument']}")
                        
                        # Extract the latest stop loss and take profit pips as scalar values
                        stop_loss_pips = float(df['stop_loss_pips'].iloc[-1])
                        take_profit_pips = float(df['take_profit_pips'].iloc[-1])

                        fill_info = self.place_order(
                            self.strategy_params['instrument'],
                            -self.strategy_params['trade_units'],
                            stop_loss_pips,
                            take_profit_pips
                        )

                        if fill_info:
                            self.logger.info(f"SHORT order filled: {fill_info}")
                            self.last_trade_exit_time = datetime.datetime.now(datetime.UTC)
                            self.cooldown_active = True
                            self.logger.info("Entering cooldown period after trade")
                            # TODO: Need to verify cooldown logic and detect trade closure

                    else:
                        self.logger.info("No entry signal detected")

                # Wait before next check
                self.logger.info(f"Sleeping for {sleep_duration} seconds.")
                time.sleep(sleep_duration)

            except KeyboardInterrupt:
                self.logger.info("Trader stopped manually")
                break

            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(60)