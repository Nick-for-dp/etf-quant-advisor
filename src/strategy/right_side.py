"""右侧趋势交易策略.

右侧交易（Trend Following）的核心思想：
    放弃抄底逃顶，等待趋势确认后跟进。

================================================================================
策略逻辑梳理
================================================================================

输入：
    - indicators: List[IndicatorModel] - 最近N个交易日的技术指标（按日期升序）
    - quote: QuoteModel - 最新价格数据（含溢价率）
    - entry_price: Optional[Decimal] - 持仓成本价（可选，用于止损判断）
    - highest_price: Optional[Decimal] - 持仓期间最高价（可选，用于移动止盈）

计算过程：
    买入信号检查：
        1. 趋势确认：ADX > 25 且 +DI > -DI
        2. 均线多头：MA5 > MA10 > MA20
        3. MACD金叉：DIF上穿DEA 且 DIF > 0
        4. 成交量确认：volume_ratio > 1.2
        5. 非超买：RSI < 70
        6. 溢价率风控：check_premium_risk() 返回 BUY

    卖出信号检查：
        1. 趋势反转：close < MA20 且 MA20走平或向下
        2. MACD死叉：DIF下穿DEA
        3. 硬止损：亏损 > 8%
        4. 移动止盈：从最高点回撤 > 5%

输出：
    - SignalModel：BUY / SELL / HOLD

================================================================================
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

from src.data.models.indicator import IndicatorModel
from src.data.models.quote import QuoteModel
from src.data.models.signal import SignalModel
from src.strategy.risk_control import check_premium_risk, SuggestAction, RiskCheckResult
from src.utils import get_logger


logger = get_logger(__name__)


# ==================== 数据类定义 ====================

@dataclass
class BuySignalCheck:
    """买入信号检查结果."""
    passed: bool                              # 是否通过
    trend_confirmed: bool                     # 趋势确认
    ma_bullish: bool                          # 均线多头
    macd_golden_cross: bool                   # MACD金叉
    volume_confirmed: bool                    # 成交量确认
    not_overbought: bool                      # 非超买
    risk_check: RiskCheckResult               # 风控检查结果
    score: int                                # 信号强度评分（0-5）
    score_details: List[str]                  # 评分细节


@dataclass
class SellSignalCheck:
    """卖出信号检查结果."""
    triggered: bool                           # 是否触发卖出
    trend_reversal: bool                      # 趋势反转
    macd_death_cross: bool                    # MACD死叉
    hard_stop_loss: bool                      # 硬止损
    trailing_stop: bool                       # 移动止盈
    trigger_reason: Optional[str] = None      # 触发原因


# ==================== 买入信号判断 ====================

def check_buy_signal(
    indicators: List[IndicatorModel],
    quote: QuoteModel,
) -> BuySignalCheck:
    """检查买入信号条件.

    Args:
        indicators: 最近N个交易日的指标数据（按日期升序，[-1]为最新）
        quote: 最新价格数据（含溢价率）

    Returns:
        BuySignalCheck: 买入信号检查结果
    """
    # 需要至少2天的指标数据（用于判断MACD金叉）
    if len(indicators) < 2:
        logger.warning("指标数据不足，需要至少2天")
        return _create_failed_buy_check("指标数据不足")

    latest = indicators[-1]
    prev = indicators[-2]

    # 1. 趋势确认：ADX > 25 且 +DI > -DI
    trend_confirmed = _check_trend_confirmation(latest)

    # 2. 均线多头：MA5 > MA10 > MA20
    ma_bullish = _check_ma_bullish(latest)

    # 3. MACD金叉：DIF上穿DEA 且 DIF > 0
    macd_golden_cross = _check_macd_golden_cross(latest, prev)

    # 4. 成交量确认：volume_ratio > 1.2
    volume_confirmed = _check_volume_confirmation(latest)

    # 5. 非超买：RSI < 70
    not_overbought = _check_not_overbought(latest)

    # 6. 溢价率风控
    risk_check = check_premium_risk(quote.premium_rate)

    # 计算信号强度评分
    score, score_details = _calculate_buy_score(
        ma_bullish=ma_bullish,
        macd_golden_cross=macd_golden_cross,
        volume_confirmed=volume_confirmed,
        rsi=latest.rsi_6,
    )

    # 综合判断：所有技术条件满足 + 风控建议买入 + 评分 >= 3
    all_conditions_met = (
        trend_confirmed and
        ma_bullish and
        macd_golden_cross and
        volume_confirmed and
        not_overbought
    )

    passed = all_conditions_met and risk_check.suggest_action == SuggestAction.BUY and score >= 3

    return BuySignalCheck(
        passed=passed,
        trend_confirmed=trend_confirmed,
        ma_bullish=ma_bullish,
        macd_golden_cross=macd_golden_cross,
        volume_confirmed=volume_confirmed,
        not_overbought=not_overbought,
        risk_check=risk_check,
        score=score,
        score_details=score_details,
    )


def _check_trend_confirmation(indicator: IndicatorModel) -> bool:
    """检查趋势确认条件：ADX > 25 且 +DI > -DI."""
    if indicator.adx is None or indicator.adx_plus_di is None or indicator.adx_minus_di is None:
        return False
    return indicator.adx > 25 and indicator.adx_plus_di > indicator.adx_minus_di


def _check_ma_bullish(indicator: IndicatorModel) -> bool:
    """检查均线多头排列：MA5 > MA10 > MA20."""
    if indicator.ma5 is None or indicator.ma10 is None or indicator.ma20 is None:
        return False
    return indicator.ma5 > indicator.ma10 > indicator.ma20


def _check_macd_golden_cross(latest: IndicatorModel, prev: IndicatorModel) -> bool:
    """检查MACD金叉：DIF上穿DEA 且 DIF > 0."""
    if latest.macd_dif is None or latest.macd_dea is None:
        return False
    if prev.macd_dif is None or prev.macd_dea is None:
        return False

    # 前一日 DIF < DEA，当日 DIF > DEA（金叉）
    cross_up = prev.macd_dif < prev.macd_dea and latest.macd_dif > latest.macd_dea
    # DIF > 0（多头区域）
    above_zero = latest.macd_dif > 0

    return cross_up and above_zero


def _check_volume_confirmation(indicator: IndicatorModel) -> bool:
    """检查成交量确认：volume_ratio > 1.2."""
    if indicator.volume_ratio is None:
        return False
    return indicator.volume_ratio > Decimal("1.2")


def _check_not_overbought(indicator: IndicatorModel) -> bool:
    """检查非超买：RSI < 70."""
    if indicator.rsi_6 is None:
        return False
    return indicator.rsi_6 < 70


def _calculate_buy_score(
    ma_bullish: bool,
    macd_golden_cross: bool,
    volume_confirmed: bool,
    rsi: Optional[Decimal],
) -> Tuple[int, List[str]]:
    """计算买入信号强度评分.

    评分规则：
        - 均线多头排列: +2分
        - MACD金叉: +2分
        - 成交量放大: +1分
        - RSI < 60: +1分（更加安全）

    Returns:
        (score, details): 评分和评分细节
    """
    score = 0
    details = []

    if ma_bullish:
        score += 2
        details.append("均线多头排列(+2)")
    else:
        details.append("均线未形成多头排列(0)")

    if macd_golden_cross:
        score += 2
        details.append("MACD金叉(+2)")
    else:
        details.append("MACD未金叉(0)")

    if volume_confirmed:
        score += 1
        details.append("成交量放大(+1)")

    if rsi is not None and rsi < 60:
        score += 1
        details.append("RSI安全区(+1)")

    return score, details


def _create_failed_buy_check(reason: str) -> BuySignalCheck:
    """创建失败的买入检查结果."""
    return BuySignalCheck(
        passed=False,
        trend_confirmed=False,
        ma_bullish=False,
        macd_golden_cross=False,
        volume_confirmed=False,
        not_overbought=False,
        risk_check=check_premium_risk(None),
        score=0,
        score_details=[reason],
    )


# ==================== 卖出信号判断 ====================

def check_sell_signal(
    indicators: List[IndicatorModel],
    quote: QuoteModel,
    entry_price: Optional[Decimal] = None,
    highest_price: Optional[Decimal] = None,
) -> SellSignalCheck:
    """检查卖出信号条件.

    Args:
        indicators: 最近N个交易日的指标数据
        quote: 最新价格数据
        entry_price: 持仓成本价（用于计算止损）
        highest_price: 持仓期间最高价（用于移动止盈）

    Returns:
        SellSignalCheck: 卖出信号检查结果
    """
    if len(indicators) < 2:
        logger.warning("指标数据不足，需要至少2天")
        return SellSignalCheck(
            triggered=False,
            trend_reversal=False,
            macd_death_cross=False,
            hard_stop_loss=False,
            trailing_stop=False,
        )

    latest = indicators[-1]
    prev = indicators[-2]

    # 1. 趋势反转：close < MA20 且 MA20走平或向下
    trend_reversal = _check_trend_reversal(latest, prev, quote)

    # 2. MACD死叉：DIF下穿DEA
    macd_death_cross = _check_macd_death_cross(latest, prev)

    # 3. 硬止损：亏损 > 8%
    hard_stop_loss = _check_hard_stop_loss(quote.close_px, entry_price)

    # 4. 移动止盈：从最高点回撤 > 5%
    trailing_stop = _check_trailing_stop(quote.close_px, highest_price)

    # 判断是否触发卖出
    triggered = trend_reversal or macd_death_cross or hard_stop_loss or trailing_stop

    # 确定触发原因
    trigger_reason = None
    if triggered:
        reasons = []
        if trend_reversal:
            reasons.append("趋势反转")
        if macd_death_cross:
            reasons.append("MACD死叉")
        if hard_stop_loss:
            reasons.append("触发止损")
        if trailing_stop:
            reasons.append("移动止盈")
        trigger_reason = "、".join(reasons)

    return SellSignalCheck(
        triggered=triggered,
        trend_reversal=trend_reversal,
        macd_death_cross=macd_death_cross,
        hard_stop_loss=hard_stop_loss,
        trailing_stop=trailing_stop,
        trigger_reason=trigger_reason,
    )


def _check_trend_reversal(
    latest: IndicatorModel,
    prev: IndicatorModel,
    quote: QuoteModel,
) -> bool:
    """检查趋势反转：close < MA20 且 MA20走平或向下."""
    if latest.ma20 is None or prev.ma20 is None:
        return False
    if quote.close_px is None:
        return False

    # 收盘价跌破MA20
    below_ma20 = quote.close_px < latest.ma20
    # MA20走平或向下（当日MA20 <= 前一日MA20）
    ma20_flat_or_down = latest.ma20 <= prev.ma20

    return below_ma20 and ma20_flat_or_down


def _check_macd_death_cross(latest: IndicatorModel, prev: IndicatorModel) -> bool:
    """检查MACD死叉：DIF下穿DEA."""
    if latest.macd_dif is None or latest.macd_dea is None:
        return False
    if prev.macd_dif is None or prev.macd_dea is None:
        return False

    # 前一日 DIF > DEA，当日 DIF < DEA（死叉）
    return prev.macd_dif > prev.macd_dea and latest.macd_dif < latest.macd_dea


def _check_hard_stop_loss(
    close_px: Optional[Decimal],
    entry_price: Optional[Decimal],
) -> bool:
    """检查硬止损：亏损 > 8%."""
    if entry_price is None or close_px is None:
        return False
    loss_pct = (entry_price - close_px) / entry_price
    return loss_pct > Decimal("0.08")


def _check_trailing_stop(
    close_px: Optional[Decimal],
    highest_price: Optional[Decimal],
) -> bool:
    """检查移动止盈：从最高点回撤 > 5%."""
    if highest_price is None or close_px is None:
        return False
    drawdown = (highest_price - close_px) / highest_price
    return drawdown > Decimal("0.05")


# ==================== 信号生成 ====================

def generate_buy_signal(
    etf_code: str,
    indicators: List[IndicatorModel],
    quote: QuoteModel,
    strategy_id: Optional[int] = 1,
) -> Optional[SignalModel]:
    """生成买入信号.

    Args:
        etf_code: ETF代码
        indicators: 指标数据
        quote: 价格数据
        strategy_id: 策略ID

    Returns:
        SignalModel 或 None（条件不满足时）
    """
    check_result = check_buy_signal(indicators, quote)

    if not check_result.passed:
        logger.debug(f"ETF {etf_code} 买入条件不满足，评分: {check_result.score}")
        return None

    if check_result.score < 4:
        logger.info(f"ETF {etf_code} 买入信号较弱，评分: {check_result.score}，建议观望")
        return None

    # 计算建议参数
    entry_price = quote.close_px
    atr = indicators[-1].atr_14
    ma20 = indicators[-1].ma20

    # 止损价：入场价 - 2 * ATR
    stop_loss = None
    if entry_price and atr:
        stop_loss = entry_price - 2 * atr

    # 目标价：入场价 + 15%
    target_price = None
    if entry_price:
        target_price = entry_price * Decimal("1.15")

    # 置信度：评分 / 5
    confidence = Decimal(str(check_result.score)) / Decimal("5")

    # 触发条件描述
    trigger_condition = "、".join(check_result.score_details)

    signal = SignalModel(
        etf_code=etf_code,
        strategy_id=strategy_id,
        signal_type="BUY",
        time_frame="1D",
        trigger_price=entry_price,
        trigger_condition=trigger_condition,
        suggested_entry=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        position_pct=Decimal("0.3"),  # 默认30%仓位
        confidence=confidence,
        invalidation_price=ma20,  # 跌破MA20则信号失效
        notes=f"信号强度: {'★' * check_result.score}{'☆' * (5 - check_result.score)}",
    )

    logger.info(f"ETF {etf_code} 生成买入信号，评分: {check_result.score}，置信度: {confidence:.2f}")
    return signal


def generate_sell_signal(
    etf_code: str,
    indicators: List[IndicatorModel],
    quote: QuoteModel,
    entry_price: Optional[Decimal] = None,
    highest_price: Optional[Decimal] = None,
    strategy_id: Optional[int] = 1,
) -> Optional[SignalModel]:
    """生成卖出信号.

    Args:
        etf_code: ETF代码
        indicators: 指标数据
        quote: 价格数据
        entry_price: 持仓成本价
        highest_price: 持仓期间最高价
        strategy_id: 策略ID

    Returns:
        SignalModel 或 None（条件不满足时）
    """
    check_result = check_sell_signal(indicators, quote, entry_price, highest_price)

    if not check_result.triggered:
        return None

    signal = SignalModel(
        etf_code=etf_code,
        strategy_id=strategy_id,
        signal_type="SELL",
        time_frame="1D",
        trigger_price=quote.close_px,
        trigger_condition=check_result.trigger_reason,
        notes=f"卖出原因: {check_result.trigger_reason}",
    )

    logger.info(f"ETF {etf_code} 生成卖出信号，原因: {check_result.trigger_reason}")
    return signal


def generate_hold_signal(
    etf_code: str,
    quote: QuoteModel,
    strategy_id: Optional[int] = 1,
) -> SignalModel:
    """生成持有信号.

    当买入和卖出条件都不满足时，返回持有信号。
    """
    return SignalModel(
        etf_code=etf_code,
        strategy_id=strategy_id,
        signal_type="HOLD",
        time_frame="1D",
        trigger_price=quote.close_px,
        trigger_condition="持有观望",
        notes="当前无明确交易信号",
    )
