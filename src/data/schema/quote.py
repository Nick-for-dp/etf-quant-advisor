"""ETF 价格数据 Schema.

对应数据库表: etf_quotes
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.data.schema.base import Base


def now_bj():
    """返回北京时间（Asia/Shanghai）."""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class ETFQuote(Base):
    """ETF每日价格数据表.

    存储ETF的日K线数据，包括OHLC价格、成交量、换手率、净值、溢价率等。

    Attributes:
        etf_code: ETF代码，外键关联etfs表
        trade_date: 交易日期
        open_px: 开盘价（使用_px后缀避免保留字冲突）
        high_px: 最高价
        low_px: 最低价
        close_px: 收盘价
        volume: 成交量
        amount: 成交金额
        turnover: 换手率
        nav: 基金净值
        premium_rate: 溢价率
        created_at: 创建时间
    """

    __tablename__ = "etf_quotes"

    etf_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("etfs.etf_code", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # 价格数据（OHLC）- _px后缀避免与Python/SQL保留字冲突
    open_px: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    high_px: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    low_px: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    close_px: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # 成交量能
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(16, 2))
    turnover: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    # ETF特有指标
    nav: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    premium_rate: Mapped[Optional[float]] = mapped_column(Numeric(8, 6))

    # 交易状态（0=停牌，1=正常交易）
    trade_status: Mapped[int] = mapped_column(Integer, default=1, comment="交易状态：0停牌，1正常")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj
    )

    def __repr__(self) -> str:
        return f"<ETFQuote(code={self.etf_code}, date={self.trade_date})>"