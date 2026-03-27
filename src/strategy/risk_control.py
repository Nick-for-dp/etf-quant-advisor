"""溢价率风控模块.

提供 ETF 溢价率风险判断功能。

溢价率 = (收盘价 - 单位净值) / 单位净值 × 100%

风控阈值（参考 README.md）：
    - > 10%：极高溢价，禁止买入
    - 5% - 10%：高溢价，警示
    - 2% - 5%：轻度溢价，可接受
    - -2% - 2%：合理区间，最佳交易区间
    - -5% - -2%：折价，可能出现价值机会
    - < -5%：深度折价，关注套利机会或流动性风险
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class PremiumLevel(Enum):
    """溢价率等级枚举."""

    EXTREME_HIGH = "extreme_high"   # > 10%：极高溢价
    HIGH = "high"                   # 5% - 10%：高溢价
    LIGHT_HIGH = "light_high"       # 2% - 5%：轻度溢价
    REASONABLE = "reasonable"       # -2% - 2%：合理区间
    DISCOUNT = "discount"           # -5% - -2%：折价
    DEEP_DISCOUNT = "deep_discount" # < -5%：深度折价
    UNKNOWN = "unknown"             # 溢价率缺失


class SuggestAction(Enum):
    """建议操作枚举."""

    BUY = "buy"       # 建议买入
    HOLD = "hold"     # 持有/观望
    REDUCE = "reduce" # 建议减仓


@dataclass
class RiskCheckResult:
    """风控检查结果.

    Attributes:
        level: 溢价率等级
        suggest_action: 建议操作（BUY/HOLD/REDUCE）
        warning: 风险警告信息（如有）
        suggestion: 操作建议
    """
    level: PremiumLevel
    suggest_action: SuggestAction
    warning: Optional[str] = None
    suggestion: Optional[str] = None


def get_premium_level(premium_rate: Optional[Decimal]) -> PremiumLevel:
    """判断溢价率等级.

    Args:
        premium_rate: 溢价率（百分比形式，如 3.5 表示 3.5%）

    Returns:
        溢价率等级枚举值

    Example:
        >>> get_premium_level(Decimal("8.5"))
        <PremiumLevel.HIGH: 'high'>
        >>> get_premium_level(Decimal("-3.0"))
        <PremiumLevel.DISCOUNT: 'discount'>
    """
    if premium_rate is None:
        return PremiumLevel.UNKNOWN

    if premium_rate > 10:
        return PremiumLevel.EXTREME_HIGH
    elif premium_rate > 5:
        return PremiumLevel.HIGH
    elif premium_rate > 2:
        return PremiumLevel.LIGHT_HIGH
    elif premium_rate >= -2:
        return PremiumLevel.REASONABLE
    elif premium_rate >= -5:
        return PremiumLevel.DISCOUNT
    else:
        return PremiumLevel.DEEP_DISCOUNT


def check_premium_risk(premium_rate: Optional[Decimal]) -> RiskCheckResult:
    """检查溢价率风险.

    根据溢价率判断建议操作，覆盖买入/持有/卖出全场景。

    Args:
        premium_rate: 溢价率（百分比形式）

    Returns:
        RiskCheckResult: 包含建议操作、风险等级、警告信息

    Example:
        >>> result = check_premium_risk(Decimal("12.0"))
        >>> result.suggest_action
        <SuggestAction.REDUCE: 'reduce'>
        >>> result.warning
        '溢价率过高(12.00%)，存在较大回撤风险'

        >>> result = check_premium_risk(Decimal("-2.5"))
        >>> result.suggest_action
        <SuggestAction.BUY: 'buy'>
        >>> result.suggestion
        '折价交易，可能出现价值机会'
    """
    level = get_premium_level(premium_rate)

    if level == PremiumLevel.UNKNOWN:
        return RiskCheckResult(
            level=level,
            suggest_action=SuggestAction.HOLD,
            warning="溢价率数据缺失，无法进行溢价率风控",
            suggestion="建议确认净值数据是否正常",
        )

    if level == PremiumLevel.EXTREME_HIGH:
        return RiskCheckResult(
            level=level,
            suggest_action=SuggestAction.REDUCE,
            warning=f"溢价率过高({premium_rate:.2f}%)，存在较大回撤风险",
            suggestion="禁止买入，已有持仓建议减仓",
        )

    if level == PremiumLevel.HIGH:
        return RiskCheckResult(
            level=level,
            suggest_action=SuggestAction.HOLD,
            warning=f"溢价率较高({premium_rate:.2f}%)，买入需谨慎",
            suggestion="不建议追高，等待溢价率回落",
        )

    if level == PremiumLevel.LIGHT_HIGH:
        return RiskCheckResult(
            level=level,
            suggest_action=SuggestAction.HOLD,
            warning=None,
            suggestion="溢价率可接受，正常交易",
        )

    if level == PremiumLevel.REASONABLE:
        return RiskCheckResult(
            level=level,
            suggest_action=SuggestAction.BUY,
            warning=None,
            suggestion="溢价率合理，最佳交易区间",
        )

    if level == PremiumLevel.DISCOUNT:
        return RiskCheckResult(
            level=level,
            suggest_action=SuggestAction.BUY,
            warning=None,
            suggestion="折价交易，可能出现价值机会",
        )

    # DEEP_DISCOUNT
    return RiskCheckResult(
        level=level,
        suggest_action=SuggestAction.BUY,
        warning=f"深度折价({premium_rate:.2f}%)，关注流动性风险",
        suggestion="可能存在套利机会，但需关注流动性",
    )


def format_premium_rate(premium_rate: Optional[Decimal]) -> str:
    """格式化溢价率显示.

    Args:
        premium_rate: 溢价率（百分比形式）

    Returns:
        格式化后的字符串

    Example:
        >>> format_premium_rate(Decimal("3.50"))
        '+3.50%'
        >>> format_premium_rate(Decimal("-2.00"))
        '-2.00%'
        >>> format_premium_rate(None)
        'N/A'
    """
    if premium_rate is None:
        return "N/A"

    sign = "+" if premium_rate >= 0 else ""
    return f"{sign}{premium_rate:.2f}%"


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        Decimal("12.5"),   # 极高溢价
        Decimal("7.0"),    # 高溢价
        Decimal("3.5"),    # 轻度溢价
        Decimal("0.5"),    # 合理区间
        Decimal("-3.0"),   # 折价
        Decimal("-7.5"),   # 深度折价
        None,              # 缺失
    ]

    print("=== 溢价率风险检查 ===")
    for rate in test_cases:
        result = check_premium_risk(rate)
        print(f"溢价率: {format_premium_rate(rate):>8} | "
              f"等级: {result.level.value:12} | "
              f"建议: {result.suggest_action.value}")
        if result.warning:
            print(f"  警告: {result.warning}")
        if result.suggestion:
            print(f"  说明: {result.suggestion}")
