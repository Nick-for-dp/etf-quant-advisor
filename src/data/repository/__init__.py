"""数据仓库模块.

提供各数据模型的 CRUD 操作，面向业务场景设计。
所有方法接收 Session 参数，由调用方管理会话生命周期。

Usage:
    >>> from src.data.database import db_session
    >>> from src.data.repository import ETFRepository, SignalRepository
    >>>
    >>> with db_session() as db:
    ...     etfs = ETFRepository.get_all_etfs(db)
    ...     signals = SignalRepository.get_active_signals(db)
"""

from src.data.repository.etf_repo import ETFRepository
from src.data.repository.quote_repo import QuoteRepository
from src.data.repository.indicator_repo import IndicatorRepository
from src.data.repository.strategy_repo import StrategyRepository
from src.data.repository.signal_repo import SignalRepository
from src.data.repository.performance_repo import PerformanceRepository

__all__ = [
    "ETFRepository",
    "QuoteRepository",
    "IndicatorRepository",
    "StrategyRepository",
    "SignalRepository",
    "PerformanceRepository",
]