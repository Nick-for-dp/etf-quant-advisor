"""ETF 基础信息 Schema.

对应数据库表: etfs
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import String, Numeric, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.data.schema.base import Base


def now_bj():
    """返回北京时间（Asia/Shanghai）."""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class ETF(Base):
    """ETF基础信息表.

    存储ETF的基本信息，如代码、名称、市场、类别等。

    Attributes:
        etf_code: ETF代码，主键，如"510300"
        etf_name: ETF名称
        market: 市场代码，默认"CN"
        category: 类别，如宽基、行业、商品等
        tracking_index: 跟踪指数名称
        fund_company: 基金公司简称
        aum: 资产规模（亿元）
        expense_ratio: 费率（小数表示）
        inception_date: 成立日期
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "etfs"

    etf_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    etf_name: Mapped[str] = mapped_column(String(50), nullable=False)
    market: Mapped[str] = mapped_column(String(2), default="CN")
    category: Mapped[Optional[str]] = mapped_column(String(20))
    tracking_index: Mapped[Optional[str]] = mapped_column(String(60))
    fund_company: Mapped[Optional[str]] = mapped_column(String(30))
    aum: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    expense_ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    inception_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj, onupdate=now_bj
    )

    def __repr__(self) -> str:
        return f"<ETF(code={self.etf_code}, name={self.etf_name})>"