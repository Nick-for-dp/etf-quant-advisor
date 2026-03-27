"""ETF 价格数据业务模型.

用于日终数据采集场景，从 AKShare 采集 ETF 日线数据。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator

from src.data.schema import ETFQuote


def parse_trade_date(value: Union[str, date]) -> date:
    """解析交易日期字符串为 date 对象.

    支持多种格式：
        - "2024-01-15" (ISO 格式)
        - "20240115" (紧凑格式)
        - "2024/01/15" (斜杠格式)

    Args:
        value: 日期字符串或 date 对象

    Returns:
        date 对象

    Raises:
        ValueError: 无法解析的日期格式
    """
    if isinstance(value, date):
        return value

    value = str(value).strip()

    # 尝试不同格式
    formats = [
        "%Y-%m-%d",  # 2024-01-15
        "%Y%m%d",    # 20240115
        "%Y/%m/%d",  # 2024/01/15
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"无法解析日期: {value}")


def format_trade_date(value: date, fmt: str = "%Y-%m-%d") -> str:
    """将 date 对象格式化为字符串.

    Args:
        value: date 对象
        fmt: 输出格式，默认 "%Y-%m-%d"

    Returns:
        格式化后的日期字符串
    """
    return value.strftime(fmt)


class QuoteModel(BaseModel):
    """ETF 价格数据业务模型.

    Attributes:
        etf_code: ETF 代码
        trade_date: 交易日期（字符串格式，如 "2024-01-15" 或 "20240115"）
        open_px: 开盘价
        high_px: 最高价
        low_px: 最低价
        close_px: 收盘价
        volume: 成交量（股）
        amount: 成交金额（元）
        turnover: 换手率
        nav: 基金净值
        premium_rate: 溢价率
    """

    etf_code: str = Field(..., max_length=8, description="ETF代码")
    trade_date: str = Field(..., description="交易日期")
    open_px: Optional[Decimal] = Field(None, description="开盘价")
    high_px: Optional[Decimal] = Field(None, description="最高价")
    low_px: Optional[Decimal] = Field(None, description="最低价")
    close_px: Optional[Decimal] = Field(None, description="收盘价")
    volume: Optional[int] = Field(None, description="成交量(股)")
    amount: Optional[Decimal] = Field(None, description="成交金额(元)")
    turnover: Optional[Decimal] = Field(None, description="换手率")
    nav: Optional[Decimal] = Field(None, description="基金净值")
    premium_rate: Optional[Decimal] = Field(None, description="溢价率")
    trade_status: int = Field(1, description="交易状态：0停牌，1正常")

    @field_validator("trade_date", mode="before")
    @classmethod
    def normalize_trade_date(cls, v) -> str:
        """规范化交易日期为字符串格式.

        确保存储时统一为 "YYYY-MM-DD" 格式。
        """
        if isinstance(v, date):
            return format_trade_date(v)
        # 尝试解析并格式化
        parsed = parse_trade_date(v)
        return format_trade_date(parsed)

    def get_trade_date(self) -> date:
        """获取交易日期的 date 对象.

        Returns:
            date 对象
        """
        return parse_trade_date(self.trade_date)

    def to_schema(self) -> ETFQuote:
        """转换为 ORM Schema.

        Returns:
            ETFQuote ORM 实例
        """
        data = self.model_dump()
        data["trade_date"] = self.get_trade_date()
        return ETFQuote(**data)

    @classmethod
    def from_schema(cls, schema: ETFQuote) -> "QuoteModel":
        """从 ORM Schema 转换.

        Args:
            schema: ETFQuote ORM 实例

        Returns:
            QuoteModel 实例
        """
        data = {
            "etf_code": schema.etf_code,
            "trade_date": format_trade_date(schema.trade_date),
            "open_px": schema.open_px,
            "high_px": schema.high_px,
            "low_px": schema.low_px,
            "close_px": schema.close_px,
            "volume": schema.volume,
            "amount": schema.amount,
            "turnover": schema.turnover,
            "nav": schema.nav,
            "premium_rate": schema.premium_rate,
            "trade_status": schema.trade_status,
        }
        return cls(**data)