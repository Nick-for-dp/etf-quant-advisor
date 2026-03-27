"""交易信号业务模型.

用于信号生成场景。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.data.schema import Signal


class SignalModel(BaseModel):
    """交易信号业务模型.

    Attributes:
        etf_code: ETF 代码
        strategy_id: 关联策略 ID
        signal_type: 信号类型（BUY/SELL/HOLD）
        time_frame: 适用周期（1D/60M/15M）
        trigger_price: 触发价格
        trigger_condition: 触发条件描述
        suggested_entry: 建议入场价
        stop_loss: 建议止损价
        target_price: 建议目标价
        position_pct: 建议仓位比例
        confidence: 置信度（0-1）
        invalidation_price: 信号失效价
        valid_until: 信号有效期至
        notes: 备注
    """

    etf_code: str = Field(..., max_length=8, description="ETF代码")
    strategy_id: Optional[int] = Field(None, description="策略ID")
    signal_type: str = Field(..., max_length=6, description="信号类型")
    time_frame: str = Field(default="1D", max_length=4, description="时间周期")

    # 触发条件
    trigger_price: Decimal = Field(..., description="触发价格")
    trigger_condition: Optional[str] = Field(None, max_length=200, description="触发条件")

    # 建议参数
    suggested_entry: Optional[Decimal] = Field(None, description="建议入场价")
    stop_loss: Optional[Decimal] = Field(None, description="止损价")
    target_price: Optional[Decimal] = Field(None, description="目标价")
    position_pct: Optional[Decimal] = Field(None, description="仓位比例")

    # 信号质量
    confidence: Optional[Decimal] = Field(None, ge=0, le=1, description="置信度")
    invalidation_price: Optional[Decimal] = Field(None, description="失效价")
    valid_until: Optional[date] = Field(None, description="有效期至")

    # 备注
    notes: Optional[str] = Field(None, max_length=500, description="备注")

    def to_schema(self) -> Signal:
        """转换为 ORM Schema.

        Returns:
            Signal ORM 实例
        """
        return Signal(**self.model_dump())

    @classmethod
    def from_schema(cls, schema: Signal) -> "SignalModel":
        """从 ORM Schema 转换.

        Args:
            schema: Signal ORM 实例

        Returns:
            SignalModel 实例
        """
        data = {
            "etf_code": schema.etf_code,
            "strategy_id": schema.strategy_id,
            "signal_type": schema.signal_type,
            "time_frame": schema.time_frame,
            "trigger_price": schema.trigger_price,
            "trigger_condition": schema.trigger_condition,
            "suggested_entry": schema.suggested_entry,
            "stop_loss": schema.stop_loss,
            "target_price": schema.target_price,
            "position_pct": schema.position_pct,
            "confidence": schema.confidence,
            "invalidation_price": schema.invalidation_price,
            "valid_until": schema.valid_until,
            "notes": schema.notes,
        }
        return cls(**data)