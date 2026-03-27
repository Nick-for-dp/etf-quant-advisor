"""技术指标业务模型.

用于指标计算完成后保存场景。
"""

from datetime import date
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator

from src.data.schema import ETFIndicator
from src.data.models.quote import parse_trade_date, format_trade_date


class IndicatorModel(BaseModel):
    """技术指标业务模型.

    Attributes:
        etf_code: ETF 代码
        trade_date: 交易日期（字符串格式，如 "2024-01-15" 或 "20240115"）
        ma5: 5日均线
        ma10: 10日均线
        ma20: 20日均线
        ma60: 60日均线
        macd_dif: MACD DIF 线
        macd_dea: MACD DEA 线
        macd_bar: MACD 柱状图
        rsi_6: 6日 RSI
        rsi_12: 12日 RSI
        rsi_24: 24日 RSI
        boll_upper: 布林带上轨
        boll_mid: 布林带中轨
        boll_lower: 布林带下轨
        atr_14: 14日 ATR
        adx: ADX 趋势强度
        adx_plus_di: ADX +DI
        adx_minus_di: ADX -DI
        volume_ma5: 5日成交量均线
        volume_ma20: 20日成交量均线
        volume_ratio: 量比
    """

    etf_code: str = Field(..., max_length=8, description="ETF代码")
    trade_date: str = Field(..., description="交易日期")

    # 均线指标
    ma5: Optional[Decimal] = Field(None, description="5日均线")
    ma10: Optional[Decimal] = Field(None, description="10日均线")
    ma20: Optional[Decimal] = Field(None, description="20日均线")
    ma60: Optional[Decimal] = Field(None, description="60日均线")

    # MACD 指标
    macd_dif: Optional[Decimal] = Field(None, description="MACD DIF")
    macd_dea: Optional[Decimal] = Field(None, description="MACD DEA")
    macd_bar: Optional[Decimal] = Field(None, description="MACD柱")

    # RSI 指标
    rsi_6: Optional[Decimal] = Field(None, description="6日RSI")
    rsi_12: Optional[Decimal] = Field(None, description="12日RSI")
    rsi_24: Optional[Decimal] = Field(None, description="24日RSI")

    # 布林带
    boll_upper: Optional[Decimal] = Field(None, description="布林上轨")
    boll_mid: Optional[Decimal] = Field(None, description="布林中轨")
    boll_lower: Optional[Decimal] = Field(None, description="布林下轨")

    # ATR
    atr_14: Optional[Decimal] = Field(None, description="14日ATR")

    # ADX
    adx: Optional[Decimal] = Field(None, description="ADX趋势强度")
    adx_plus_di: Optional[Decimal] = Field(None, description="ADX +DI")
    adx_minus_di: Optional[Decimal] = Field(None, description="ADX -DI")

    # 成交量指标
    volume_ma5: Optional[int] = Field(None, description="5日成交量均线")
    volume_ma20: Optional[int] = Field(None, description="20日成交量均线")
    volume_ratio: Optional[Decimal] = Field(None, description="量比")

    @field_validator("trade_date", mode="before")
    @classmethod
    def normalize_trade_date(cls, v) -> str:
        """规范化交易日期为字符串格式.

        确保存储时统一为 "YYYY-MM-DD" 格式。
        """
        if isinstance(v, date):
            return format_trade_date(v)
        parsed = parse_trade_date(v)
        return format_trade_date(parsed)

    def get_trade_date(self) -> date:
        """获取交易日期的 date 对象.

        Returns:
            date 对象
        """
        return parse_trade_date(self.trade_date)

    def to_schema(self) -> ETFIndicator:
        """转换为 ORM Schema.

        Returns:
            ETFIndicator ORM 实例
        """
        data = self.model_dump()
        data["trade_date"] = self.get_trade_date()
        return ETFIndicator(**data)

    @classmethod
    def from_schema(cls, schema: ETFIndicator) -> "IndicatorModel":
        """从 ORM Schema 转换.

        Args:
            schema: ETFIndicator ORM 实例

        Returns:
            IndicatorModel 实例
        """
        data = {
            "etf_code": schema.etf_code,
            "trade_date": format_trade_date(schema.trade_date),
            "ma5": schema.ma5,
            "ma10": schema.ma10,
            "ma20": schema.ma20,
            "ma60": schema.ma60,
            "macd_dif": schema.macd_dif,
            "macd_dea": schema.macd_dea,
            "macd_bar": schema.macd_bar,
            "rsi_6": schema.rsi_6,
            "rsi_12": schema.rsi_12,
            "rsi_24": schema.rsi_24,
            "boll_upper": schema.boll_upper,
            "boll_mid": schema.boll_mid,
            "boll_lower": schema.boll_lower,
            "atr_14": schema.atr_14,
            "adx": schema.adx,
            "adx_plus_di": schema.adx_plus_di,
            "adx_minus_di": schema.adx_minus_di,
            "volume_ma5": schema.volume_ma5,
            "volume_ma20": schema.volume_ma20,
            "volume_ratio": schema.volume_ratio,
        }
        return cls(**data)