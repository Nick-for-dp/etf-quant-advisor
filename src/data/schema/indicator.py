"""技术指标 Schema.

对应数据库表: etf_indicators
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.data.schema.base import Base


def now_bj():
    """返回北京时间（Asia/Shanghai）."""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class ETFIndicator(Base):
    """ETF技术指标表.

    存储计算出的技术指标，面向右侧交易优化。
    包含均线、MACD、RSI、布林带、ATR、ADX、成交量指标等。

    Attributes:
        etf_code: ETF代码，外键关联etfs表
        trade_date: 交易日期
        ma5/ma10/ma20/ma60: 移动平均线
        macd_dif/dea/bar: MACD指标
        rsi_6/rsi_12/rsi_24: RSI多周期指标
        boll_upper/mid/lower: 布林带
        atr_14: 平均真实波幅（用于止损距离）
        adx: 趋势强度（右侧交易核心）
        adx_plus_di/minus_di: DMI方向指标
        volume_ma5/volume_ma20: 成交量均线
        volume_ratio: 量比
        created_at: 创建时间
    """

    __tablename__ = "etf_indicators"

    etf_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("etfs.etf_code", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # 均线指标（趋势判断）
    ma5: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    ma10: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    ma20: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    ma60: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # MACD指标（趋势动量）
    macd_dif: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    macd_dea: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    macd_bar: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # RSI指标（超买超卖）
    rsi_6: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    rsi_12: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    rsi_24: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))

    # 布林带（波动区间）
    boll_upper: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    boll_mid: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    boll_lower: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # ATR指标（波动率，用于设置止损/目标价）
    atr_14: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # ADX指标（趋势强度，右侧交易核心）
    adx: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    adx_plus_di: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    adx_minus_di: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))

    # 成交量指标（趋势确认）
    volume_ma5: Mapped[Optional[int]] = mapped_column(BigInteger)
    volume_ma20: Mapped[Optional[int]] = mapped_column(BigInteger)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_bj
    )

    def __repr__(self) -> str:
        return f"<ETFIndicator(code={self.etf_code}, date={self.trade_date})>"