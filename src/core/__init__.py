"""核心模块.

提供每日运行流程编排和数据完整性检查功能。
"""

from src.core.daily_runner import DailyRunner, RunStatus, DailyRunResult
from src.core.evening_runner import EveningRunner, EveningStatus, EveningRunResult
from src.core.data_integrity import DataIntegrityChecker, IntegrityCheckResult


__all__ = [
    # Morning Job
    "DailyRunner",
    "RunStatus",
    "DailyRunResult",
    # Evening Job
    "EveningRunner",
    "EveningStatus",
    "EveningRunResult",
    # Data Integrity
    "DataIntegrityChecker",
    "IntegrityCheckResult",
]