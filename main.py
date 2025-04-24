import oandapyV20
from trader import OandaTrader
import os
from dotenv import load_dotenv

if __name__ == "__main__":

    load_dotenv()

    OANDA_API_KEY = os.getenv("OANDA_API_KEY")
    OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
    OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT")

    api = oandapyV20.API(access_token=OANDA_API_KEY, environment=OANDA_ENVIRONMENT)

    # Example indicator functions
    def calculate_atr(df, params):
        return df

    def calculate_adx(df, params):
        return df

    # Signal calculation function
    def calculate_signals(df, params):
        return df

    strategy_params = {
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

    # Initialize trader with custom functions
    trader = OandaTrader(
        api=api,
        account_id=OANDA_ACCOUNT_ID,
        strategy_params=strategy_params,
        calculate_signals_function=calculate_signals,
        indicator_functions={
            'atr': calculate_atr,
            'adx': calculate_adx
        }
    )

    trader.run_trader()