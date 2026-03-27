"""ETF 基础信息业务模型.

用于数据源同步场景，从 AKShare 采集 ETF 基础信息。
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.data.schema import ETF


class ETFModel(BaseModel):
    """ETF 基础信息业务模型.

    Attributes:
        etf_code: ETF 代码，如 "510300"
        etf_name: ETF 名称
        market: 市场代码，默认 "CN"
        category: 类别，如宽基、行业、商品等
        tracking_index: 跟踪指数名称
        fund_company: 基金公司简称
        aum: 资产规模（亿元）
        expense_ratio: 费率（小数表示）
        inception_date: 成立日期
    """

    etf_code: str = Field(..., max_length=8, description="ETF代码")
    etf_name: str = Field(..., max_length=50, description="ETF名称")
    market: str = Field(default="CN", max_length=2, description="市场代码")
    category: Optional[str] = Field(None, max_length=20, description="类别")
    tracking_index: Optional[str] = Field(None, max_length=60, description="跟踪指数")
    fund_company: Optional[str] = Field(None, max_length=30, description="基金公司")
    aum: Optional[Decimal] = Field(None, description="资产规模(亿元)")
    expense_ratio: Optional[Decimal] = Field(None, description="费率")
    inception_date: Optional[date] = Field(None, description="成立日期")

    def to_schema(self) -> ETF:
        """转换为 ORM Schema.

        Returns:
            ETF ORM 实例
        """
        return ETF(**self.model_dump())

    @classmethod
    def from_schema(cls, schema: ETF) -> "ETFModel":
        """从 ORM Schema 转换.

        Args:
            schema: ETF ORM 实例

        Returns:
            ETFModel 实例
        """
        # 提取业务字段，排除 SQLAlchemy 内部属性和时间戳
        data = {
            "etf_code": schema.etf_code,
            "etf_name": schema.etf_name,
            "market": schema.market,
            "category": schema.category,
            "tracking_index": schema.tracking_index,
            "fund_company": schema.fund_company,
            "aum": schema.aum,
            "expense_ratio": schema.expense_ratio,
            "inception_date": schema.inception_date,
        }
        return cls(**data)
