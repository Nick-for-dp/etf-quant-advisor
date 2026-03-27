"""技术指标计算模块.

提供 ETF 技术指标的计算功能。

重要说明：
    指标只对交易日（trade_status=1）进行计算。
    停牌日（trade_status=0）不计算指标，也不存储到数据库。
    这样策略层获取的指标数据天然就是交易日数据。
"""

from decimal import Decimal
from typing import List

import pandas as pd

from src.analysis.momentum import calc_macd, calc_rsi
from src.analysis.trend import calc_adx, calc_ma
from src.analysis.volatility import calc_atr, calc_boll
from src.analysis.volume import calc_volume_indicators
from src.utils import get_logger
from src.data.models.indicator import IndicatorModel
from src.data.models.quote import QuoteModel

logger = get_logger(__name__)


def calculate_all_indicators(
    quotes: List[QuoteModel],
) -> List[IndicatorModel]:
    """计算所有技术指标的主入口.

    整合所有指标计算模块，从价格数据生成完整的技术指标。

    重要：
        只对交易日（trade_status=1）计算指标。
        停牌日（trade_status=0）的指标不计算也不存储，原因：
        1. 停牌日 volume=0，volume_ratio=0，会导致指标失真
        2. 停牌日 high=low=close，TR≈0，会导致 ATR/ADX 计算错误
        3. 右侧交易信号不应在停牌日生成

    Args:
        quotes: 价格数据列表，按日期升序排列（可能包含停牌日填充数据）

    Returns:
        指标数据列表（仅包含交易日，停牌日不返回）

    Example:
        >>> quotes = QuoteRepository.get_recent_quotes(db, "510300", limit=60)
        >>> quote_models = [QuoteModel.from_schema(q) for q in quotes]
        >>> indicators = calculate_all_indicators(quote_models)
    """

    if not quotes:
        return []

    # 1. 转换为 DataFrame
    df = pd.DataFrame([q.model_dump() for q in quotes])

    # 2. 过滤停牌日：只对交易日计算指标
    # trade_status=1 表示正常交易，trade_status=0 表示停牌
    trading_df = df[df['trade_status'] == 1].copy().reset_index(drop=True)

    if trading_df.empty:
        logger.warning("无交易日数据，无法计算指标")
        return []

    original_count = len(df)
    trading_count = len(trading_df)
    if trading_count < original_count:
        logger.info(
            f"过滤停牌日数据：原始 {original_count} 天 -> 交易日 {trading_count} 天"
        )

    # 3. 确保价格字段为 float 类型
    trading_df['close_px'] = trading_df['close_px'].astype(float)
    trading_df['high_px'] = trading_df['high_px'].astype(float)
    trading_df['low_px'] = trading_df['low_px'].astype(float)
    trading_df['volume'] = trading_df['volume'].astype(float)

    # 4. 批量计算各指标（仅使用交易日数据）
    trading_df = calc_ma(trading_df)
    trading_df = calc_adx(trading_df)
    trading_df = calc_macd(trading_df)
    trading_df = calc_rsi(trading_df)
    trading_df = calc_boll(trading_df)
    trading_df = calc_atr(trading_df)
    trading_df = calc_volume_indicators(trading_df)

    # 5. 转换为 IndicatorModel 列表（仅返回交易日）
    indicators = _df_to_models(trading_df)

    logger.info(f"指标计算完成：{len(indicators)} 个交易日")
    return indicators


def _df_to_models(df: pd.DataFrame) -> List[IndicatorModel]:
    """将 DataFrame 转换为 IndicatorModel 列表.

    Args:
        df: 包含所有指标列的 DataFrame

    Returns:
        IndicatorModel 列表
    """
    # 指标字段列表（与各模块输出一致）
    indicator_fields = [
        'ma5', 'ma10', 'ma20', 'ma60',
        'macd_dif', 'macd_dea', 'macd_bar',
        'rsi_6', 'rsi_12', 'rsi_24',
        'boll_upper', 'boll_mid', 'boll_lower',
        'atr_14',
        'adx', 'adx_plus_di', 'adx_minus_di',
        'volume_ma5', 'volume_ma20', 'volume_ratio',
    ]

    indicators: List[IndicatorModel] = []

    for _, row in df.iterrows():
        # 构建指标数据字典
        data = {
            'etf_code': row['etf_code'],
            'trade_date': row['trade_date'],
        }

        # 添加各指标字段，NaN 转为 None
        for field in indicator_fields:
            if field in row.index:
                value = row[field]
                if pd.isna(value):
                    data[field] = None
                elif field in ('volume_ma5', 'volume_ma20'):
                    # 成交量均线为整数
                    data[field] = int(value) if not pd.isna(value) else None
                else:
                    # 其他指标保留 Decimal 精度
                    data[field] = Decimal(str(round(value, 4)))

        indicators.append(IndicatorModel(**data))

    return indicators
