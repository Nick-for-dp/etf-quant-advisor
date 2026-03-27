"""策略配置 Schema.

对应数据库表: strategies
"""

from datetime import datetime
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

from sqlalchemy import String, Numeric, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.data.schema.base import Base


def now_bj():
    """返回北京时间（Asia/Shanghai）."""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class Strategy(Base):
    """策略配置表.

    存储交易策略的配置参数，支持JSONB灵活配置。

    Attributes:
        id: 策略ID，主键
        strategy_name: 策略名称
        strategy_desc: 策略描述
        strategy_type: 策略类型（RIGHT_TREND/BREAKOUT/PULLBACK）
        params: 策略参数（JSON格式）
        default_position_pct: 默认仓位比例
        default_stop_loss_pct: 默认止损比例
        default_target_pct: 默认目标比例
        is_active: 是否激活
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(30), nullable=False)
    strategy_desc: Mapped[Optional[str]] = mapped_column(String(200))
    strategy_type: Mapped[str] = mapped_column(String(12), nullable=False)

    # 策略参数（JSON格式，灵活配置）
    params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=dict
    )

    # 风控参数
    default_position_pct: Mapped[float] = mapped_column(
        Numeric(4, 3), default=0.3
    )
    default_stop_loss_pct: Mapped[float] = mapped_column(
        Numeric(5, 4), default=0.05
    )
    default_target_pct: Mapped[float] = mapped_column(
        Numeric(5, 4), default=0.15
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj, onupdate=now_bj
    )

    def __repr__(self) -> str:
        return f"<Strategy(id={self.id}, name={self.strategy_name}, type={self.strategy_type})>"