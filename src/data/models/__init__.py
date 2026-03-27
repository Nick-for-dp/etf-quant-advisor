"""业务数据模型模块.

提供 Pydantic 数据模型，用于数据采集、处理和传输。
与数据库 Schema 分离，专注于业务领域模型。

所有模型提供 to_schema() 和 from_schema() 方法实现与 ORM 的双向转换。

Example:
    >>> from src.data.models import ETFModel, QuoteModel, parse_trade_date
    >>> from src.data.database import db_session
    >>> from src.data.repository import ETFRepository
    >>>
    >>> # 从原始数据构建模型
    >>> raw_data = {"etf_code": "510300", "etf_name": "沪深300ETF"}
    >>> etf = ETFModel(**raw_data)
    >>>
    >>> # 转换为 ORM 并入库
    >>> with db_session() as db:
    ...     ETFRepository.upsert_etf(db, etf.to_schema())
    >>>
    >>> # 日期字符串处理
    >>> quote = QuoteModel(etf_code="510300", trade_date="20240115", ...)
    >>> print(quote.trade_date)  # "2024-01-15" (自动规范化)
    >>> print(quote.get_trade_date())  # date(2024, 1, 15)
"""

from src.data.models.etf import ETFModel
from src.data.models.quote import QuoteModel, parse_trade_date, format_trade_date
from src.data.models.indicator import IndicatorModel
from src.data.models.signal import SignalModel
from src.data.models.performance import PerformanceModel

__all__ = [
    "ETFModel",
    "QuoteModel",
    "IndicatorModel",
    "SignalModel",
    "PerformanceModel",
    # 日期工具函数
    "parse_trade_date",
    "format_trade_date",
]