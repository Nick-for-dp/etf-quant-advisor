"""收盘后性能追踪任务模块.

执行收盘后的信号性能追踪更新。

完整流程：
1. 检查是否为交易日
2. 同步 T 日收盘数据
3. 初始化 PENDING_INIT 记录
4. 更新 ACTIVE 记录的收益、极值、目标达成
5. 输出更新摘要

运行时间：
    建议每日 15:30 执行（收盘后）
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from src.core.data_integrity import DataIntegrityChecker
from src.data.database import db_session
from src.data.service.performance_service import PerformanceService, UpdateResult
from src.data.service.quote_service import QuoteService
from src.data.service.trading_calendar_service import TradingCalendarService
from src.utils import get_logger


logger = get_logger(__name__)


class EveningStatus(Enum):
    """收盘后任务状态枚举."""

    SUCCESS = "success"
    PARTIAL = "partial"  # 部分成功
    FAILED = "failed"
    SKIPPED = "skipped"  # 非交易日跳过


@dataclass
class EveningRunResult:
    """收盘后任务运行结果.

    Attributes:
        status: 运行状态
        signal_date: 信号日期（T 日）
        run_date: 运行日期
        start_time: 开始时间
        end_time: 结束时间
        quotes_synced: 同步的行情数据条数
        performances_init: 初始化的 performance 记录数
        performances_updated: 更新的 performance 记录数
        performances_completed: 完成的 performance 记录数
        errors: 错误信息列表
    """

    status: EveningStatus
    signal_date: Optional[date]
    run_date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    quotes_synced: int = 0
    performances_init: int = 0
    performances_updated: int = 0
    performances_completed: int = 0
    errors: List[str] = field(default_factory=list)


class EveningRunner:
    """收盘后性能追踪任务编排器.

    每日收盘后执行，更新信号性能追踪数据。

    运行时间窗口：
        - 建议在 15:30 后执行（A股 15:00 收盘）
        - 过早执行可能获取不到当日数据
    """

    RECOMMENDED_RUN_TIME = "15:30"

    @classmethod
    def run(cls, force: bool = False) -> EveningRunResult:
        """执行收盘后任务.

        Args:
            force: 强制运行（忽略交易日检查）

        Returns:
            EveningRunResult: 运行结果

        Example:
            >>> result = EveningRunner.run()
            >>> print(f"状态: {result.status.value}")
            >>> print(f"初始化: {result.performances_init}")
            >>> print(f"更新: {result.performances_updated}")
        """
        start_time = datetime.now()
        run_date = start_time.date()
        errors: List[str] = []

        logger.info("=" * 60)
        logger.info("开始执行收盘后性能追踪任务")
        logger.info("=" * 60)

        # 1. 获取 T 日（今日）
        signal_date = run_date

        logger.info(f"信号日期: {signal_date}")

        # 2. 判断是否为交易日
        if not force:
            calendar = TradingCalendarService()
            is_trading_day = calendar.is_trading_day(signal_date)

            if not is_trading_day:
                logger.info(f"{signal_date} 不是交易日，跳过执行")
                return EveningRunResult(
                    status=EveningStatus.SKIPPED,
                    signal_date=signal_date,
                    run_date=run_date,
                    start_time=start_time,
                    end_time=datetime.now(),
                )

        # 3. 同步 T 日收盘数据
        quotes_synced = 0
        try:
            quotes_result = cls._sync_quotes(signal_date)
            quotes_synced = quotes_result.get("quotes_count", 0)

            if quotes_result.get("status") != "success":
                errors.append(f"行情数据同步失败: {quotes_result.get('errors', [])}")
        except Exception as e:
            logger.error(f"行情数据同步异常: {e}")
            errors.append(f"行情数据同步异常: {e}")

        # 4. 初始化 PENDING_INIT 记录
        performances_init = 0
        try:
            with db_session() as db:
                performances_init = PerformanceService.init_pending_performances(
                    db, signal_date
                )
        except Exception as e:
            logger.error(f"初始化 performance 记录失败: {e}")
            errors.append(f"初始化 performance 记录失败: {e}")

        # 5. 更新 ACTIVE 记录
        update_result = UpdateResult()
        try:
            with db_session() as db:
                update_result = PerformanceService.update_active_performances(
                    db, signal_date
                )
        except Exception as e:
            logger.error(f"更新 performance 记录失败: {e}")
            errors.append(f"更新 performance 记录失败: {e}")

        # 6. 确定最终状态
        end_time = datetime.now()
        if errors and quotes_synced == 0:
            status = EveningStatus.FAILED
        elif errors:
            status = EveningStatus.PARTIAL
        else:
            status = EveningStatus.SUCCESS

        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"执行完成: 状态={status.value}, 耗时={duration:.1f}秒, "
            f"初始化={performances_init}, 更新={update_result.updated_count}, "
            f"完成={update_result.completed_count}"
        )

        return EveningRunResult(
            status=status,
            signal_date=signal_date,
            run_date=run_date,
            start_time=start_time,
            end_time=end_time,
            quotes_synced=quotes_synced,
            performances_init=performances_init,
            performances_updated=update_result.updated_count,
            performances_completed=update_result.completed_count,
            errors=errors,
        )

    @classmethod
    def _sync_quotes(cls, signal_date: date) -> dict:
        """同步行情数据.

        Args:
            signal_date: 信号日期

        Returns:
            同步结果
        """
        logger.info(f"开始同步行情数据: {signal_date}")

        result = QuoteService.sync_single_day(target_date=signal_date, save_db=True)

        logger.info(
            f"行情数据同步完成: {result['quotes_count']} 条, "
            f"耗时 {result['duration_seconds']:.1f}秒"
        )

        return result


if __name__ == "__main__":
    result = EveningRunner.run(force=True)
    print(f"\n状态: {result.status.value}")
    print(f"信号日期: {result.signal_date}")
    print(f"行情同步: {result.quotes_synced}")
    print(f"初始化: {result.performances_init}")
    print(f"更新: {result.performances_updated}")
    print(f"完成: {result.performances_completed}")
    if result.errors:
        print(f"错误: {result.errors}")