import oandapyV20
from trader import OandaTrader
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import pandas_ta as ta
import datetime

# Function to calculate EMAs and SMA
def calculate_ema_indicators(df, params):
    """Calculate EMA and SMA indicators for the strategy"""

    if 'close' in df.columns:
        close_col = 'close'
        high_col = 'high'
        low_col = 'low'
    else:
        # Default column names from the notebook
        close_col = 'Close'
        high_col = 'High'
        low_col = 'Low'
    
    # Calculate EMAs and SMA
    df['EMA_6'] = ta.ema(df[close_col], length=6)
    df['SMA_50'] = ta.sma(df[close_col], length=50)
    df['EMA_200'] = ta.ema(df[close_col], length=200)
    
    # Calculate swing points for stop loss
    window_size = params.get('swing_window', 7)  # Default to 7 bars
    df['Swing_Low'] = df[low_col].rolling(window=window_size).min()
    df['Swing_High'] = df[high_col].rolling(window=window_size).max()
    df['Prev_Swing_Low'] = df['Swing_Low'].shift(1)
    df['Prev_Swing_High'] = df['Swing_High'].shift(1)
    
    return df

# Function to calculate ADX
def calculate_adx(df, params):
    """Calculate ADX indicator"""
    if 'close' in df.columns:
        close_col = 'close'
        high_col = 'high'
        low_col = 'low'
    else:
        # Default column names
        close_col = 'Close'
        high_col = 'High'
        low_col = 'Low'
    
    # Calculate ADX with pandas_ta
    adx_period = params.get('adx_period', 14)
    adx_result = ta.adx(df[high_col], df[low_col], df[close_col], length=adx_period)
    
    # Add ADX to dataframe
    df['ADX'] = adx_result[f'ADX_{adx_period}']
    
    return df

# Signal calculation function implementing the EMA crossover strategy
def calculate_signals(df, params):
    """Calculate trading signals based on EMA crossover strategy"""
    # Initialize signal column
    df['signal'] = 0  # 0 for no signal, 1 for buy, -1 for sell
    

    if 'close' in df.columns:
        close_col = 'close'
    else:
        close_col = 'Close'
    
    # Required fields
    required_fields = ['EMA_6', 'SMA_50', 'EMA_200', 'ADX', 'Prev_Swing_Low', 'Prev_Swing_High']
    missing_fields = [field for field in required_fields if field not in df.columns]
    
    if missing_fields:
        print(f"Missing required fields: {missing_fields}")
        return df
    
    # Get strategy parameters
    adx_threshold = params.get('adx_threshold', 15)
    risk_reward_ratio = params.get('risk_reward_ratio', 4)  # Default 1:4 risk-reward
    
    # Calculate crossovers (current bar crossed above/below)
    golden_cross = (df['EMA_6'].shift(1) < df['SMA_50'].shift(1)) & (df['EMA_6'] > df['SMA_50']) 
    death_cross = (df['EMA_6'].shift(1) > df['SMA_50'].shift(1)) & (df['EMA_6'] < df['SMA_50'])
    
    # Initialize SL and TP columns
    df['stop_loss'] = np.nan
    df['take_profit'] = np.nan
    
    # Buy signals (golden cross + above 200 EMA + ADX filter)
    buy_conditions = (
        golden_cross &
        (df[close_col] > df['EMA_200']) &
        (df['ADX'] > adx_threshold)
    )
    
    df.loc[buy_conditions, 'signal'] = 1
    df.loc[buy_conditions, 'stop_loss'] = df.loc[buy_conditions, 'Prev_Swing_Low']
    
    # Calculate TP for buy signals (entry price + risk_reward_ratio * (entry price - SL))
    buy_indices = df.index[buy_conditions]
    for idx in buy_indices:
        entry_price = df.loc[idx, close_col]
        sl_price = df.loc[idx, 'stop_loss']
        if not pd.isna(sl_price) and sl_price < entry_price:
            risk = entry_price - sl_price
            df.loc[idx, 'take_profit'] = entry_price + (risk * risk_reward_ratio)
    
    # Sell signals (death cross + below 200 EMA + ADX filter)
    sell_conditions = (
        death_cross &
        (df[close_col] < df['EMA_200']) &
        (df['ADX'] > adx_threshold)
    )
    
    df.loc[sell_conditions, 'signal'] = -1
    df.loc[sell_conditions, 'stop_loss'] = df.loc[sell_conditions, 'Prev_Swing_High']
    
    # Calculate TP for sell signals (entry price - risk_reward_ratio * (SL - entry price))
    sell_indices = df.index[sell_conditions]
    for idx in sell_indices:
        entry_price = df.loc[idx, close_col]
        sl_price = df.loc[idx, 'stop_loss']
        if not pd.isna(sl_price) and sl_price > entry_price:
            risk = sl_price - entry_price
            df.loc[idx, 'take_profit'] = entry_price - (risk * risk_reward_ratio)
    
    # Convert SL and TP to pips for the trader
    if 'stop_loss' in df.columns and 'take_profit' in df.columns:
        # Convert price levels to pips
        df['stop_loss_pips'] = df.apply(
            lambda row: abs(row[close_col] - row['stop_loss']) * 10000 
            if not pd.isna(row['stop_loss']) else None, 
            axis=1
        )
        df['take_profit_pips'] = df.apply(
            lambda row: abs(row[close_col] - row['take_profit']) * 10000 
            if not pd.isna(row['take_profit']) else None, 
            axis=1
        )
    
    return df

def is_time_to_run_trader():
    current_day = datetime.date.today().weekday()
    if not (current_day >= 0 and current_day <=4):
        return False
    
    current_time = datetime.datetime.now()
    return current_time >= datetime.datetime.strptime('08:00','%H:%M') and current_time <= datetime.datetime.strptime('11:00','%H:%M')
    

if __name__ == "__main__":
    load_dotenv()

    OANDA_API_KEY = os.getenv("OANDA_API_KEY")
    OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
    OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT")

    api = oandapyV20.API(access_token=OANDA_API_KEY, environment=OANDA_ENVIRONMENT)

    # EMA crossover strategy parameters
    ema_strategy_params = {
        'pair': "EUR_USD",  # OANDA uses underscores
        'instrument': "EUR_USD",
        'granularity': "H1",  # 1-hour candles, similar to the notebook
        'cooldown_periods': 10,  # Number of bars for cooldown after a trade
        'lookback_period': 200,  # Need at least 200 bars for EMA(200)
        'swing_window': 7,  # Window for swing high/low calculation
        'adx_period': 14,  # ADX period
        'adx_threshold': 15,  # Minimum ADX value for trend filter
        'risk_reward_ratio': 3,  # 1:4 risk-reward ratio from notebook
        'trade_units': 1000  # Example trade size
    }

    trader = OandaTrader(
        api=api,
        account_id=OANDA_ACCOUNT_ID,
        strategy_params=ema_strategy_params,
        calculate_signals_function=calculate_signals,
        indicator_functions={
            'ema_indicators': calculate_ema_indicators,
            'adx': calculate_adx
        }
    )
    # print("Initializing")

    # if is_time_to_run_trader():
    print("Running trader")
    trader.run_trader(sleep_duration=60)  # Check for signals every 60 seconds