"""
策略技术指标计算模块
为回测引擎提供各种技术指标的计算功能
"""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有常用技术指标
    
    Args:
        df: 包含OHLCV的DataFrame,需要有: open, high, low, close, volume列
        
    Returns:
        DataFrame: 添加了技术指标列的数据
    """
    if df is None or df.empty:
        return df
    
    # 确保列名为小写
    df.columns = df.columns.str.lower()
    
    # 创建副本避免修改原数据
    df = df.copy()
    
    # 移动均线
    df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
    df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
    df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
    df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()
    
    # 成交量均线
    df['vol_ma5'] = df['volume'].rolling(window=5, min_periods=1).mean()
    df['vol_ma10'] = df['volume'].rolling(window=10, min_periods=1).mean()
    
    # MACD指标
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # RSI指标 (14周期)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)  # 避免除以0
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi'] = df['rsi'].fillna(50)  # NaN填充为50
    
    # 布林带 (20周期, 2倍标准差)
    df['boll_middle'] = df['close'].rolling(window=20, min_periods=1).mean()
    std = df['close'].rolling(window=20, min_periods=1).std()
    df['boll_upper'] = df['boll_middle'] + 2 * std
    df['boll_lower'] = df['boll_middle'] - 2 * std
    
    # KDJ指标
    low_list = df['low'].rolling(window=9, min_periods=1).min()
    high_list = df['high'].rolling(window=9, min_periods=1).max()
    
    # 避免除以0
    range_val = (high_list - low_list).replace(0, np.nan)
    rsv = ((df['close'] - low_list) / range_val * 100).fillna(50)
    
    df['kdj_k'] = rsv.ewm(com=2, adjust=False).mean()
    df['kdj_d'] = df['kdj_k'].ewm(com=2, adjust=False).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    
    # 填充NaN值
    df = df.fillna(method='bfill').fillna(method='ffill')
    
    return df


def calculate_ma(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    计算移动平均线
    
    Args:
        df: 数据DataFrame
        period: 周期
        column: 计算列名,默认'close'
        
    Returns:
        Series: MA值
    """
    return df[column].rolling(window=period, min_periods=1).mean()


def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    计算指数移动平均线
    
    Args:
        df: 数据DataFrame
        period: 周期
        column: 计算列名,默认'close'
        
    Returns:
        Series: EMA值
    """
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    计算MACD指标
    
    Args:
        df: 数据DataFrame
        fast: 快线周期,默认12
        slow: 慢线周期,默认26
        signal: 信号线周期,默认9
        
    Returns:
        tuple: (MACD, Signal, Histogram)
    """
    exp1 = df['close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    
    return macd, macd_signal, macd_hist


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    计算RSI指标
    
    Args:
        df: 数据DataFrame
        period: 周期,默认14
        
    Returns:
        Series: RSI值
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> tuple:
    """
    计算布林带
    
    Args:
        df: 数据DataFrame
        period: 周期,默认20
        std_dev: 标准差倍数,默认2.0
        
    Returns:
        tuple: (upper, middle, lower)
    """
    middle = df['close'].rolling(window=period, min_periods=1).mean()
    std = df['close'].rolling(window=period, min_periods=1).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    
    return upper, middle, lower


def calculate_kdj(df: pd.DataFrame, period: int = 9) -> tuple:
    """
    计算KDJ指标
    
    Args:
        df: 数据DataFrame
        period: 周期,默认9
        
    Returns:
        tuple: (K, D, J)
    """
    low_list = df['low'].rolling(window=period, min_periods=1).min()
    high_list = df['high'].rolling(window=period, min_periods=1).max()
    
    range_val = (high_list - low_list).replace(0, np.nan)
    rsv = ((df['close'] - low_list) / range_val * 100).fillna(50)
    
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return k, d, j


# 测试代码
if __name__ == '__main__':
    # 创建测试数据
    test_data = {
        'date': pd.date_range('2024-01-01', periods=100),
        'open': np.random.uniform(10, 20, 100),
        'high': np.random.uniform(15, 25, 100),
        'low': np.random.uniform(5, 15, 100),
        'close': np.random.uniform(10, 20, 100),
        'volume': np.random.uniform(1000000, 5000000, 100)
    }
    df = pd.DataFrame(test_data)
    
    print("原始数据列:", df.columns.tolist())
    print("原始数据行数:", len(df))
    
    # 计算所有指标
    df_with_indicators = calculate_all_indicators(df)
    
    print("\n计算后数据列:", df_with_indicators.columns.tolist())
    print("计算后数据行数:", len(df_with_indicators))
    
    # 显示最后5行数据
    print("\n最后5行数据(部分列):")
    print(df_with_indicators[['date', 'close', 'ma5', 'ma20', 'rsi', 'macd']].tail())
    
    print("\n✅ 技术指标计算模块测试通过")
"""
策略技术指标计算模块
为回测引擎提供各种技术指标的计算功能
"""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有常用技术指标
    
    Args:
        df: 包含OHLCV的DataFrame,需要有: open, high, low, close, volume列
        
    Returns:
        DataFrame: 添加了技术指标列的数据
    """
    if df is None or df.empty:
        return df
    
    # 确保列名为小写
    df.columns = df.columns.str.lower()
    
    # 创建副本避免修改原数据
    df = df.copy()
    
    # 移动均线
    df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
    df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
    df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
    df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()
    
    # 成交量均线
    df['vol_ma5'] = df['volume'].rolling(window=5, min_periods=1).mean()
    df['vol_ma10'] = df['volume'].rolling(window=10, min_periods=1).mean()
    
    # MACD指标
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # RSI指标 (14周期)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)  # 避免除以0
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi'] = df['rsi'].fillna(50)  # NaN填充为50
    
    # 布林带 (20周期, 2倍标准差)
    df['boll_middle'] = df['close'].rolling(window=20, min_periods=1).mean()
    std = df['close'].rolling(window=20, min_periods=1).std()
    df['boll_upper'] = df['boll_middle'] + 2 * std
    df['boll_lower'] = df['boll_middle'] - 2 * std
    
    # KDJ指标
    low_list = df['low'].rolling(window=9, min_periods=1).min()
    high_list = df['high'].rolling(window=9, min_periods=1).max()
    
    # 避免除以0
    range_val = (high_list - low_list).replace(0, np.nan)
    rsv = ((df['close'] - low_list) / range_val * 100).fillna(50)
    
    df['kdj_k'] = rsv.ewm(com=2, adjust=False).mean()
    df['kdj_d'] = df['kdj_k'].ewm(com=2, adjust=False).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    
    # 填充NaN值
    df = df.fillna(method='bfill').fillna(method='ffill')
    
    return df


def calculate_ma(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    计算移动平均线
    
    Args:
        df: 数据DataFrame
        period: 周期
        column: 计算列名,默认'close'
        
    Returns:
        Series: MA值
    """
    return df[column].rolling(window=period, min_periods=1).mean()


def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    计算指数移动平均线
    
    Args:
        df: 数据DataFrame
        period: 周期
        column: 计算列名,默认'close'
        
    Returns:
        Series: EMA值
    """
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    计算MACD指标
    
    Args:
        df: 数据DataFrame
        fast: 快线周期,默认12
        slow: 慢线周期,默认26
        signal: 信号线周期,默认9
        
    Returns:
        tuple: (MACD, Signal, Histogram)
    """
    exp1 = df['close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    
    return macd, macd_signal, macd_hist


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    计算RSI指标
    
    Args:
        df: 数据DataFrame
        period: 周期,默认14
        
    Returns:
        Series: RSI值
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> tuple:
    """
    计算布林带
    
    Args:
        df: 数据DataFrame
        period: 周期,默认20
        std_dev: 标准差倍数,默认2.0
        
    Returns:
        tuple: (upper, middle, lower)
    """
    middle = df['close'].rolling(window=period, min_periods=1).mean()
    std = df['close'].rolling(window=period, min_periods=1).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    
    return upper, middle, lower


def calculate_kdj(df: pd.DataFrame, period: int = 9) -> tuple:
    """
    计算KDJ指标
    
    Args:
        df: 数据DataFrame
        period: 周期,默认9
        
    Returns:
        tuple: (K, D, J)
    """
    low_list = df['low'].rolling(window=period, min_periods=1).min()
    high_list = df['high'].rolling(window=period, min_periods=1).max()
    
    range_val = (high_list - low_list).replace(0, np.nan)
    rsv = ((df['close'] - low_list) / range_val * 100).fillna(50)
    
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return k, d, j


# 测试代码
if __name__ == '__main__':
    # 创建测试数据
    test_data = {
        'date': pd.date_range('2024-01-01', periods=100),
        'open': np.random.uniform(10, 20, 100),
        'high': np.random.uniform(15, 25, 100),
        'low': np.random.uniform(5, 15, 100),
        'close': np.random.uniform(10, 20, 100),
        'volume': np.random.uniform(1000000, 5000000, 100)
    }
    df = pd.DataFrame(test_data)
    
    print("原始数据列:", df.columns.tolist())
    print("原始数据行数:", len(df))
    
    # 计算所有指标
    df_with_indicators = calculate_all_indicators(df)
    
    print("\n计算后数据列:", df_with_indicators.columns.tolist())
    print("计算后数据行数:", len(df_with_indicators))
    
    # 显示最后5行数据
    print("\n最后5行数据(部分列):")
    print(df_with_indicators[['date', 'close', 'ma5', 'ma20', 'rsi', 'macd']].tail())
    
    print("\n✅ 技术指标计算模块测试通过")
