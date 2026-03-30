"""信号性能追踪 Schema.

对应数据库表: signal_performance
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Numeric, DateTime, ForeignKey, Integer, Boolean, String, Date
)
from sqlalchemy.orm import Mapped, mapped_column

from src.data.schema.base import Base


def now_bj():
    """返回北京时间（Asia/Shanghai）."""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class SignalPerformance(Base):
    """信号性能追踪表.

    自动生成复盘数据，追踪信号发出后的表现。
    包含收益追踪、极值追踪、目标达成、最大回撤等。

    Attributes:
        id: 性能记录ID，主键
        signal_id: 关联信号ID
        etf_code: ETF代码，冗余存储便于查询
        hold_start_date: 持仓开始日期（reference_price对应的日期）
        performance_status: 追踪状态（pending_init/active/completed/expired）
        reference_price: 信号基准价
        return_1d/3d/5d/10d/20d: 多周期收益
        max_price_1d/3d/5d/10d/20d: 期间最高价
        min_price_1d/3d/5d/10d/20d: 期间最低价
        hit_target: 是否触及目标价
        hit_target_days: 触及目标所需天数
        hit_stop_loss: 是否触及止损
        hit_stop_loss_days: 触及止损所需天数
        max_drawdown_5d/20d: 最大回撤
        executed_price: 实际执行价（用户可选录入）
        executed_at: 实际执行时间
        executed_return: 实际收益
        score: 系统评分（1-10）
        calculated_at: 计算时间
        updated_at: 更新时间
    """

    __tablename__ = "signal_performance"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), nullable=False
    )
    etf_code: Mapped[str] = mapped_column(String(8), nullable=False)

    # 追踪状态
    hold_start_date: Mapped[Optional[date]] = mapped_column(Date)
    performance_status: Mapped[str] = mapped_column(
        String(16), default="pending_init"
    )

    # 基准价格（信号生成时的价格）
    reference_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # 后续表现（相对于 reference_price 的涨跌幅）
    return_1d: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    return_3d: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    return_5d: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    return_10d: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    return_20d: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))

    # 极值追踪（持仓后N日内的极值）
    max_price_1d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    min_price_1d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    max_price_3d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    min_price_3d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    max_price_5d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    min_price_5d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    max_price_10d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    min_price_10d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    max_price_20d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    min_price_20d: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # 目标达成情况
    hit_target: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_target_days: Mapped[Optional[int]] = mapped_column(Integer)
    hit_stop_loss: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_stop_loss_days: Mapped[Optional[int]] = mapped_column(Integer)

    # 最大回撤
    max_drawdown_5d: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    max_drawdown_20d: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))

    # 实际执行（用户可选录入）
    executed_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    executed_return: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))

    # 评分（系统根据表现自动评分）
    score: Mapped[Optional[int]] = mapped_column(Integer)

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj, onupdate=now_bj
    )

    def __repr__(self) -> str:
        return f"<SignalPerformance(signal_id={self.signal_id}, etf_code={self.etf_code}, status={self.performance_status})>"