"""交易信号 Schema.

对应数据库表: signals
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import (
    String, Numeric, Date, DateTime, ForeignKey, Integer
)
from sqlalchemy.orm import Mapped, mapped_column

from src.data.schema.base import Base


def now_bj():
    """返回北京时间（Asia/Shanghai）."""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class Signal(Base):
    """交易信号表.

    存储助手生成的交易建议，是系统的核心输出。
    包含触发条件、建议参数、信号质量、状态管理等。

    Attributes:
        id: 信号ID，主键
        etf_code: ETF代码
        strategy_id: 关联策略ID
        signal_type: 信号类型（BUY/SELL/HOLD）
        time_frame: 适用周期（1D/60M/15M）
        trigger_price: 信号触发时的价格
        trigger_condition: 触发条件描述
        suggested_entry: 建议入场价
        stop_loss: 建议止损价
        target_price: 建议目标价
        position_pct: 建议仓位比例
        confidence: 置信度0-1
        invalidation_price: 信号失效价
        valid_until: 信号有效期至
        signal_status: 信号状态
        generated_at: 生成时间
        notes: 备注
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    etf_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("etfs.etf_code", ondelete="CASCADE"), nullable=False
    )
    strategy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL")
    )

    # 信号基本信息
    signal_type: Mapped[str] = mapped_column(String(6), nullable=False)
    time_frame: Mapped[str] = mapped_column(String(4), default="1D")

    # 触发条件（生成信号时的市场状态）
    trigger_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    trigger_condition: Mapped[Optional[str]] = mapped_column(String(200))

    # 建议参数（助手输出的核心建议）
    suggested_entry: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    target_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    position_pct: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))

    # 信号质量
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    invalidation_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # 有效期
    valid_until: Mapped[Optional[date]] = mapped_column(Date)

    # 信号状态 - 使用signal_status避免与SQL保留字冲突
    signal_status: Mapped[str] = mapped_column(
        String(12), default="PENDING"
    )  # PENDING/ACTIVE/EXPIRED/TRIGGERED/INVALIDATED

    # 元信息
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj
    )
    notes: Mapped[Optional[str]] = mapped_column(String(500))

    def __repr__(self) -> str:
        return (
            f"<Signal(id={self.id}, code={self.etf_code}, "
            f"type={self.signal_type}, status={self.signal_status})>"
        )