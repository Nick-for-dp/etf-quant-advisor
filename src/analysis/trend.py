"""趋势指标计算模块.

包含：
- 移动平均线（MA5/MA10/MA20/MA60）
- 平均趋向指数（ADX、+DI、-DI）
"""

import pandas as pd


def calc_ma(df: pd.DataFrame) -> pd.DataFrame:
    """计算移动平均线.

    Args:
        df: 包含 close_px 列的 DataFrame

    Returns:
        添加 ma5/ma10/ma20/ma60 列的 DataFrame
    """
    df['ma5'] = df['close_px'].rolling(window=5).mean()
    df['ma10'] = df['close_px'].rolling(window=10).mean()
    df['ma20'] = df['close_px'].rolling(window=20).mean()
    df['ma60'] = df['close_px'].rolling(window=60).mean()
    return df


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算平均趋向指数 ADX 及 +DI/-DI.

    ADX 用于衡量趋势强度，是右侧交易的核心过滤指标：
    - ADX > 25：趋势明确，适合右侧交易
    - ADX < 20：震荡市场，避免交易
    - +DI > -DI 且 ADX 上升：上升趋势确认

    Args:
        df: 包含 high_px/low_px/close_px 列的 DataFrame
        period: 计算周期，默认 14

    Returns:
        添加 adx/adx_plus_di/adx_minus_di 列的 DataFrame
    """
    high = df['high_px']
    low = df['low_px']
    close = df['close_px']

    # 计算 True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 计算 +DM 和 -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = up_move.copy()
    plus_dm[(up_move <= 0) | (up_move <= down_move)] = 0.0

    minus_dm = down_move.copy()
    minus_dm[(down_move <= 0) | (down_move <= up_move)] = 0.0

    # 平滑 TR、+DM、-DM（使用 EMA）
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=1/period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=1/period, adjust=False).mean()

    # 计算 +DI 和 -DI
    plus_di = 100 * plus_dm_smooth / atr
    minus_di = 100 * minus_dm_smooth / atr

    # 计算 DX 和 ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    df['adx_plus_di'] = plus_di
    df['adx_minus_di'] = minus_di
    df['adx'] = adx

    return df