"""动量指标计算模块.

包含：
- MACD（DIF、DEA、BAR）
- RSI（RSI6、RSI12、RSI24）
"""

import pandas as pd


def calc_macd(
    df: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    """计算 MACD 指标.

    MACD 是趋势动量指标：
    - DIF：快慢均线差，反映短期动能
    - DEA：DIF 的平滑线，作为信号线
    - BAR：柱状图，DIF 与 DEA 的差值

    金叉判定：DIF 上穿 DEA，且 DIF > 0

    Args:
        df: 包含 close_px 列的 DataFrame
        fast_period: 快线周期，默认 12
        slow_period: 慢线周期，默认 26
        signal_period: 信号线周期，默认 9

    Returns:
        添加 macd_dif/macd_dea/macd_bar 列的 DataFrame
    """
    close = df['close_px']

    # 计算 EMA
    ema_fast = close.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close.ewm(span=slow_period, adjust=False).mean()

    # 计算 DIF 和 DEA
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal_period, adjust=False).mean()

    # 计算 MACD 柱状图
    macd_bar = 2 * (dif - dea)

    df['macd_dif'] = dif
    df['macd_dea'] = dea
    df['macd_bar'] = macd_bar

    return df


def calc_rsi(df: pd.DataFrame, periods: tuple = (6, 12, 24)) -> pd.DataFrame:
    """计算 RSI 相对强弱指标.

    RSI 用于判断超买超卖：
    - RSI > 70：超买区域
    - RSI < 30：超卖区域
    - RSI < 60：相对安全（买入信号加分）

    Args:
        df: 包含 close_px 列的 DataFrame
        periods: 计算周期列表，默认 (6, 12, 24)

    Returns:
        添加 rsi_6/rsi_12/rsi_24 列的 DataFrame
    """
    close = df['close_px']
    delta = close.diff()

    # 分离上涨和下跌
    gain = delta.copy()
    gain[gain < 0] = 0
    loss = -delta.copy()
    loss[loss < 0] = 0

    # 计算各周期 RSI
    for period in periods:
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        df[f'rsi_{period}'] = rsi

    return df