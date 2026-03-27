"""成交量指标计算模块.

包含：
- 成交量均线（volume_ma5、volume_ma20）
- 量比（volume_ratio）
"""

import pandas as pd


def calc_volume_indicators(
    df: pd.DataFrame,
    ma_periods: tuple = (5, 20),
) -> pd.DataFrame:
    """计算成交量相关指标.

    成交量指标用于确认价格趋势：
    - 价格上涨 + 放量：趋势确认
    - 价格上涨 + 缩量：趋势可能衰竭
    - 量比 > 1.2：成交量放大

    Args:
        df: 包含 volume 列的 DataFrame
        ma_periods: 均线周期列表，默认 (5, 20)

    Returns:
        添加 volume_ma5/volume_ma20/volume_ratio 列的 DataFrame
    """
    volume = df['volume']

    # 成交量均线
    for period in ma_periods:
        df[f"volume_ma{period}"] = volume.rolling(window=period).mean()

    # 量比 = 当日成交量 / 5日成交量均线
    df['volume_ratio'] = volume / df['volume_ma5']

    return df