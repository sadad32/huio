import pandas as pd
import numpy as np

# --- Indicator Calculation Functions ---

def calculate_ma(data: pd.DataFrame, period: int, column: str = 'close', method: str = 'SMA') -> pd.Series:
    """Calculates Moving Average (SMA or EMA)."""
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    if method == 'SMA':
        return data[column].rolling(window=period).mean()
    elif method == 'EMA':
        return data[column].ewm(span=period, adjust=False).mean()
    else:
        raise ValueError("Unsupported MA method. Use 'SMA' or 'EMA'.")

def calculate_rsi(data: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
    """Calculates Relative Strength Index (RSI)."""
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    delta = data[column].diff(1)
    gain = delta.where(delta > 0, 0).fillna(0)
    loss = -delta.where(delta < 0, 0).fillna(0)

    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    # Handle avg_loss == 0 to prevent division by zero
    rs = np.where(avg_loss == 0, np.inf, avg_gain / avg_loss) # if avg_loss is 0, rs is inf

    rsi = 100 - (100 / (1 + rs))

    # If rs was inf (due to avg_loss being 0), rsi will be 100.
    # If avg_gain is also 0 (no price change), rs could be NaN if avg_loss is also 0.
    # A common practice is to set RSI to 50 in case of no price change or start of series.
    # Or 100 if price only went up, 0 if only down (though this is handled by rs logic).
    rsi = pd.Series(rsi, index=data.index) # Ensure it's a Series for replace/fillna
    rsi = rsi.replace([np.inf, -np.inf], 100).fillna(50) # Fill NaNs (e.g. at start) with 50
    return rsi


def calculate_macd(data: pd.DataFrame, period_fast: int = 12, period_slow: int = 26, period_signal: int = 9, column: str = 'close'):
    """Calculates MACD, Signal Line, and Histogram."""
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    ema_fast = data[column].ewm(span=period_fast, adjust=False).mean()
    ema_slow = data[column].ewm(span=period_slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=period_signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_stochastic(data: pd.DataFrame, k_period: int = 14, d_period: int = 3, slowing: int = 3):
    """Calculates Stochastic Oscillator (%K and %D)."""
    if not all(col in data.columns for col in ['low', 'high', 'close']):
        raise ValueError("Dataframe must contain 'low', 'high', 'close' columns.")

    low_min = data['low'].rolling(window=k_period).min()
    high_max = data['high'].rolling(window=k_period).max()

    # Prevent division by zero if high_max == low_min
    k_line_raw = (data['close'] - low_min)
    k_line_denom = (high_max - low_min)

    k_line = np.where(k_line_denom == 0, 50.0, 100 * (k_line_raw / k_line_denom)) # Default to 50 if range is zero
    k_line = pd.Series(k_line, index=data.index).fillna(50) # Fill initial NaNs

    if slowing > 1:
        k_line = k_line.rolling(window=slowing).mean() # Apply slowing to %K

    d_line = k_line.rolling(window=d_period).mean() # %D is SMA of %K
    d_line = d_line.fillna(50) # Fill initial NaNs
    k_line = k_line.fillna(50) # Ensure K line is also filled after slowing might reintroduce NaNs at start
    return k_line, d_line

def calculate_bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev_multiplier: float = 2.0, column: str = 'close'):
    """Calculates Bollinger Bands."""
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    middle_band = data[column].rolling(window=period).mean()
    rolling_std = data[column].rolling(window=period).std()
    upper_band = middle_band + (rolling_std * std_dev_multiplier)
    lower_band = middle_band - (rolling_std * std_dev_multiplier)
    return upper_band, middle_band, lower_band

def calculate_daily_pivot_points(prev_day_data: pd.Series):
    """
    Calculates Daily Pivot Points using a single row (Series) of previous day's OHLC data.
    Expects a Pandas Series with 'high', 'low', 'close' keys.
    """
    if not all(k in prev_day_data for k in ['high', 'low', 'close']):
        raise ValueError("Previous day data must contain 'high', 'low', 'close'")

    high = prev_day_data['high']
    low = prev_day_data['low']
    close = prev_day_data['close']

    pp = (high + low + close) / 3.0
    s1 = (2.0 * pp) - high
    r1 = (2.0 * pp) - low
    s2 = pp - (high - low)
    r2 = pp + (high - low)
    s3 = low - 2.0 * (high - pp)
    r3 = high + 2.0 * (pp - low)

    return {
        "PP": pp, "S1": s1, "R1": r1, "S2": s2, "R2": r2, "S3": s3, "R3": r3
    }

def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Average True Range (ATR)."""
    if not all(col in data.columns for col in ['high', 'low', 'close']):
        raise ValueError("Dataframe must contain 'high', 'low', 'close' columns.")

    high_low = data['high'] - data['low']
    high_close_prev = np.abs(data['high'] - data['close'].shift(1))
    low_close_prev = np.abs(data['low'] - data['close'].shift(1))

    tr_df = pd.DataFrame({'hl': high_low, 'hc': high_close_prev, 'lc': low_close_prev})
    tr = tr_df.max(axis=1)

    atr = tr.ewm(alpha=1.0/period, adjust=False, min_periods=period).mean() # Using Wilder's smoothing
    return atr

if __name__ == '__main__':
    # Small test area for indicator functions
    data_size = 50
    dummy_data = pd.DataFrame({
        'time': pd.to_datetime(np.arange(data_size), unit='D', origin='2023-01-01'),
        'open': np.random.rand(data_size) * 10 + 100,
        'high': np.random.rand(data_size) * 5 + 105, # ensure high is higher
        'low': 100 - np.random.rand(data_size) * 5,   # ensure low is lower
        'close': np.random.rand(data_size) * 10 + 100,
        'tick_volume': np.random.randint(100, 1000, data_size)
    })
    # Ensure high >= open/close and low <= open/close
    dummy_data['high'] = dummy_data[['high', 'open', 'close']].max(axis=1)
    dummy_data['low'] = dummy_data[['low', 'open', 'close']].min(axis=1)
    dummy_data.set_index('time', inplace=True)


    print("--- Testing MA (SMA 10) ---")
    ma_values = calculate_ma(dummy_data, 10, method='SMA')
    print(ma_values.tail())

    print("\n--- Testing RSI (14) ---")
    rsi_values = calculate_rsi(dummy_data, 14)
    print(rsi_values.tail())

    print("\n--- Testing MACD (12,26,9) ---")
    macd_line, signal_line, _ = calculate_macd(dummy_data)
    print("MACD:", macd_line.tail())
    print("Signal:", signal_line.tail())

    print("\n--- Testing Stochastic (14,3,3) ---")
    k_line, d_line = calculate_stochastic(dummy_data, k_period=14, d_period=3, slowing=3)
    print("%K:", k_line.tail())
    print("%D:", d_line.tail())

    print("\n--- Testing Bollinger Bands (20,2) ---")
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(dummy_data, period=20, std_dev_multiplier=2.0)
    print("Upper BB:", upper_bb.tail())
    print("Middle BB:", middle_bb.tail())
    print("Lower BB:", lower_bb.tail())

    print("\n--- Testing Daily Pivot Points ---")
    if len(dummy_data) >= 2:
        prev_day_ohlc = dummy_data.iloc[-2]
        pivots = calculate_daily_pivot_points(prev_day_ohlc)
        print(pivots)
    else:
        print("Not enough data for pivot point test.")

    print("\n--- Testing ATR (14) ---")
    atr_values = calculate_atr(dummy_data, 14)
    print(atr_values.tail())
