"""交易策略模块.

提供右侧交易策略和风控功能。

模块结构：
    - risk_control: 溢价率风控模块
    - right_side: 右侧趋势交易策略
"""

from src.strategy.risk_control import (
    PremiumLevel,
    SuggestAction,
    RiskCheckResult,
    check_premium_risk,
    get_premium_level,
    format_premium_rate,
)

from src.strategy.right_side import (
    BuySignalCheck,
    SellSignalCheck,
    check_buy_signal,
    check_sell_signal,
    generate_buy_signal,
    generate_sell_signal,
    generate_hold_signal,
)


__all__ = [
    # 风控模块
    "PremiumLevel",
    "SuggestAction",
    "RiskCheckResult",
    "check_premium_risk",
    "get_premium_level",
    "format_premium_rate",
    # 右侧交易策略
    "BuySignalCheck",
    "SellSignalCheck",
    "check_buy_signal",
    "check_sell_signal",
    "generate_buy_signal",
    "generate_sell_signal",
    "generate_hold_signal",
]