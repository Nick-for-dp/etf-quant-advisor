"""波动率指标计算模块.

包含：
- 布林带（upper、mid、lower）
- ATR（平均真实波幅）
"""

import pandas as pd


def calc_boll(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
) -> pd.DataFrame:
    """计算布林带指标.

    布林带由中轨、上轨、下轨组成：
    - 中轨：N 日移动平均线
    - 上轨：中轨 + K 倍标准差
    - 下轨：中轨 - K 倍标准差

    用途：
    - 价格触及上轨：可能超买
    - 价格触及下轨：可能超卖
    - 布林带收窄：可能即将突破

    Args:
        df: 包含 close_px 列的 DataFrame
        period: 计算周期，默认 20
        std_dev: 标准差倍数，默认 2.0

    Returns:
        添加 boll_upper/boll_mid/boll_lower 列的 DataFrame
    """
    close = df['close_px']

    # 中轨 = 移动平均线
    mid = close.rolling(window=period).mean()

    # 标准差
    std = close.rolling(window=period).std()

    # 上轨和下轨
    upper = mid + std_dev * std
    lower = mid - std_dev * std

    df['boll_mid'] = mid
    df['boll_upper'] = upper
    df['boll_lower'] = lower

    return df


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算平均真实波幅 ATR.

    ATR 用于衡量价格波动幅度：
    - 用于设置合理的止损距离
    - ATR 倍数止损：Entry - 2×ATR（更适应波动率）

    Args:
        df: 包含 high_px/low_px/close_px 列的 DataFrame
        period: 计算周期，默认 14

    Returns:
        添加 atr_14 列的 DataFrame
    """
    high = df['high_px']
    low = df['low_px']
    close = df['close_px']

    # 计算 True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # ATR = TR 的移动平均
    atr = tr.rolling(window=period).mean()

    df['atr_14'] = atr

    return df