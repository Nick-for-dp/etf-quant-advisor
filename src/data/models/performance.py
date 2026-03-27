"""信号性能追踪业务模型.

用于性能追踪场景。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.data.schema import SignalPerformance


class PerformanceModel(BaseModel):
    """信号性能追踪业务模型.

    Attributes:
        signal_id: 关联信号 ID
        reference_price: 基准价格
        return_1d/3d/5d/10d/20d: 多周期收益
        max_price_5d/20d: 期间最高价
        min_price_5d/20d: 期间最低价
        hit_target: 是否触及目标价
        hit_target_days: 触及目标所需天数
        hit_stop_loss: 是否触及止损
        hit_stop_loss_days: 触及止损所需天数
        max_drawdown_5d/20d: 最大回撤
        executed_price: 实际执行价
        executed_at: 实际执行时间
        executed_return: 实际收益
        score: 系统评分（1-10）
    """

    signal_id: int = Field(..., description="信号ID")
    reference_price: Optional[Decimal] = Field(None, description="基准价格")

    # 多周期收益
    return_1d: Optional[Decimal] = Field(None, description="1日收益")
    return_3d: Optional[Decimal] = Field(None, description="3日收益")
    return_5d: Optional[Decimal] = Field(None, description="5日收益")
    return_10d: Optional[Decimal] = Field(None, description="10日收益")
    return_20d: Optional[Decimal] = Field(None, description="20日收益")

    # 极值追踪
    max_price_5d: Optional[Decimal] = Field(None, description="5日最高价")
    min_price_5d: Optional[Decimal] = Field(None, description="5日最低价")
    max_price_20d: Optional[Decimal] = Field(None, description="20日最高价")
    min_price_20d: Optional[Decimal] = Field(None, description="20日最低价")

    # 目标达成
    hit_target: bool = Field(default=False, description="是否触及目标")
    hit_target_days: Optional[int] = Field(None, description="触及目标天数")
    hit_stop_loss: bool = Field(default=False, description="是否触及止损")
    hit_stop_loss_days: Optional[int] = Field(None, description="触及止损天数")

    # 最大回撤
    max_drawdown_5d: Optional[Decimal] = Field(None, description="5日最大回撤")
    max_drawdown_20d: Optional[Decimal] = Field(None, description="20日最大回撤")

    # 实际执行
    executed_price: Optional[Decimal] = Field(None, description="执行价格")
    executed_at: Optional[datetime] = Field(None, description="执行时间")
    executed_return: Optional[Decimal] = Field(None, description="执行收益")

    # 评分
    score: Optional[int] = Field(None, ge=1, le=10, description="评分")

    def to_schema(self) -> SignalPerformance:
        """转换为 ORM Schema.

        Returns:
            SignalPerformance ORM 实例
        """
        return SignalPerformance(**self.model_dump())

    @classmethod
    def from_schema(cls, schema: SignalPerformance) -> "PerformanceModel":
        """从 ORM Schema 转换.

        Args:
            schema: SignalPerformance ORM 实例

        Returns:
            PerformanceModel 实例
        """
        data = {
            "signal_id": schema.signal_id,
            "reference_price": schema.reference_price,
            "return_1d": schema.return_1d,
            "return_3d": schema.return_3d,
            "return_5d": schema.return_5d,
            "return_10d": schema.return_10d,
            "return_20d": schema.return_20d,
            "max_price_5d": schema.max_price_5d,
            "min_price_5d": schema.min_price_5d,
            "max_price_20d": schema.max_price_20d,
            "min_price_20d": schema.min_price_20d,
            "hit_target": schema.hit_target,
            "hit_target_days": schema.hit_target_days,
            "hit_stop_loss": schema.hit_stop_loss,
            "hit_stop_loss_days": schema.hit_stop_loss_days,
            "max_drawdown_5d": schema.max_drawdown_5d,
            "max_drawdown_20d": schema.max_drawdown_20d,
            "executed_price": schema.executed_price,
            "executed_at": schema.executed_at,
            "executed_return": schema.executed_return,
            "score": schema.score,
        }
        return cls(**data)