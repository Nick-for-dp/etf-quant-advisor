"""每日核心流程编排模块.

整合数据同步、指标计算、信号生成、报告输出的完整流程。
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.data_integrity import DataIntegrityChecker
from src.data.database import db_session
from src.data.service.indicator_service import IndicatorService
from src.data.service.quote_service import QuoteService
from src.data.service.signal_service import SignalService
from src.data.service.trading_calendar_service import TradingCalendarService
from src.data.models.signal import SignalModel
from src.utils import get_logger


logger = get_logger(__name__)


class RunStatus(Enum):
    """运行状态枚举."""

    SUCCESS = "success"
    PARTIAL = "partial"  # 部分成功
    FAILED = "failed"
    SKIPPED = "skipped"  # 非交易日跳过


@dataclass
class DailyRunResult:
    """每日运行结果.

    Attributes:
        status: 运行状态
        signal_date: 信号日期（T-1）
        run_date: 运行日期（T）
        start_time: 开始时间
        end_time: 结束时间
        quotes_synced: 同步的行情数据条数
        indicators_calculated: 计算的指标条数
        signals_generated: 生成的信号数
        signals: 生成的信号列表
        report_path: 报告文件路径
        errors: 错误信息列表
        details: 详细信息
    """

    status: RunStatus
    signal_date: Optional[date]
    run_date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    quotes_synced: int = 0
    indicators_calculated: int = 0
    signals_generated: int = 0
    signals: List[SignalModel] = field(default_factory=list)
    report_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class DailyRunner:
    """每日运行流程编排器.

    完整流程：
    1. 获取 T-1 交易日
    2. 检查是否为交易日
    3. 同步 T-1 日行情数据
    4. 计算技术指标
    5. 生成交易信号
    6. 输出日报告

    运行时间窗口：
    - 最早运行时间：00:00
    - 最晚运行时间：08:30（开盘前）
    - 超过时间窗口警告但不阻止执行
    """

    EARLIEST_RUN_TIME = "00:00"
    LATEST_RUN_TIME = "08:30"

    @classmethod
    def run(
        cls,
        force: bool = False,
        output_report: bool = True,
        positions: Optional[Dict[str, Dict[str, float]]] = None,
        target_date: Optional[date] = None,
    ) -> DailyRunResult:
        """执行每日核心流程.

        Args:
            force: 强制运行（忽略时间检查和非交易日检查）
            output_report: 是否输出日报告
            positions: 持仓信息 {"etf_code": {"entry_price": x, "highest_price": y}}
            target_date: 指定目标日期，默认为 T-1 交易日

        Returns:
            DailyRunResult: 运行结果

        Example:
            >>> result = DailyRunner.run()
            >>> print(f"状态: {result.status.value}")
            >>> print(f"信号: {result.signals_generated} 个")
        """
        from decimal import Decimal

        start_time = datetime.now()
        run_date = start_time.date()
        errors: List[str] = []

        logger.info("=" * 60)
        logger.info("开始执行每日核心流程")
        logger.info("=" * 60)

        # 1. 时间检查
        if not force:
            time_check = cls._check_run_time()
            if not time_check["ok"]:
                logger.warning(f"时间检查警告: {time_check['message']}")

        # 2. 获取 T-1 交易日
        signal_date = cls._get_signal_date(target_date)
        if signal_date is None:
            return DailyRunResult(
                status=RunStatus.FAILED,
                signal_date=None,
                run_date=run_date,
                start_time=start_time,
                end_time=datetime.now(),
                errors=["无法获取前一交易日"],
            )

        logger.info(f"信号日期: {signal_date}")

        # 3. 判断是否为交易日
        calendar = TradingCalendarService()
        is_trading_day = calendar.is_trading_day(signal_date)

        if not is_trading_day and not force:
            logger.info(f"{signal_date} 不是交易日，跳过执行")
            return DailyRunResult(
                status=RunStatus.SKIPPED,
                signal_date=signal_date,
                run_date=run_date,
                start_time=start_time,
                end_time=datetime.now(),
                details={"reason": "非交易日"},
            )

        # 4. 数据完整性预检查
        integrity_result = DataIntegrityChecker.check_t1_data(signal_date)
        if not integrity_result.passed and not force:
            if integrity_result.missing_codes:
                logger.warning(f"数据缺失: {integrity_result.missing_codes}")

        # 5. 同步 T-1 日行情数据
        quotes_result = cls._sync_quotes(signal_date)
        quotes_synced = quotes_result.get("quotes_count", 0)

        if quotes_result.get("status") != "success" and not force:
            errors.append(f"行情数据同步失败: {quotes_result.get('errors', [])}")

        # 6. 计算技术指标
        indicators_result = cls._calculate_indicators()
        indicators_calculated = sum(indicators_result.values()) if indicators_result else 0

        # 7. 生成交易信号
        # 转换 positions 中的 float 为 Decimal
        decimal_positions: Optional[Dict[str, Dict[str, Decimal]]] = None
        if positions:
            decimal_positions = {}
            for code, pos in positions.items():
                decimal_positions[code] = {
                    k: Decimal(str(v)) for k, v in pos.items()
                }

        signals = cls._generate_signals(decimal_positions)
        signals_generated = len(signals)

        # 8. 输出报告
        report_path = None
        if output_report:
            report_path = cls._output_report(
                signal_date=signal_date,
                quotes_synced=quotes_synced,
                indicators_calculated=indicators_calculated,
                signals=signals,
                start_time=start_time,
                errors=errors,
            )

        # 9. 确定最终状态
        end_time = datetime.now()
        if errors and quotes_synced == 0:
            status = RunStatus.FAILED
        elif errors:
            status = RunStatus.PARTIAL
        else:
            status = RunStatus.SUCCESS

        duration = (end_time - start_time).total_seconds()
        logger.info(f"执行完成: 状态={status.value}, 耗时={duration:.1f}秒")

        return DailyRunResult(
            status=status,
            signal_date=signal_date,
            run_date=run_date,
            start_time=start_time,
            end_time=end_time,
            quotes_synced=quotes_synced,
            indicators_calculated=indicators_calculated,
            signals_generated=signals_generated,
            signals=signals,
            report_path=report_path,
            errors=errors,
            details={
                "duration_seconds": duration,
                "quotes_result": quotes_result,
                "indicators_result": indicators_result,
            },
        )

    @classmethod
    def _check_run_time(cls) -> Dict[str, Any]:
        """检查是否在允许的运行时间窗口内.

        Returns:
            {"ok": bool, "message": str}
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        if cls.EARLIEST_RUN_TIME <= current_time <= cls.LATEST_RUN_TIME:
            return {"ok": True, "message": "运行时间正常"}
        elif current_time > cls.LATEST_RUN_TIME:
            return {
                "ok": False,
                "message": f"当前时间 {current_time} 已超过 {cls.LATEST_RUN_TIME}，开盘后运行可能影响决策",
            }
        else:
            return {"ok": True, "message": "运行时间正常"}

    @classmethod
    def _get_signal_date(cls, target_date: Optional[date] = None) -> Optional[date]:
        """获取信号日期（T-1 交易日）.

        Args:
            target_date: 指定目标日期

        Returns:
            信号日期，如果无法获取则返回 None
        """
        if target_date is not None:
            return target_date

        calendar = TradingCalendarService()
        prev_day_str = calendar.get_previous_trading_day()

        if prev_day_str is None:
            return None

        return date.fromisoformat(prev_day_str)

    @classmethod
    def _sync_quotes(cls, target_date: date) -> Dict[str, Any]:
        """同步行情数据.

        Args:
            target_date: 目标日期

        Returns:
            同步结果
        """
        logger.info(f"开始同步行情数据: {target_date}")

        result = QuoteService.sync_single_day(target_date=target_date, save_db=True)

        logger.info(
            f"行情数据同步完成: {result['quotes_count']} 条, "
            f"耗时 {result['duration_seconds']:.1f}秒"
        )

        return result

    @classmethod
    def _calculate_indicators(cls) -> Dict[str, int]:
        """计算技术指标.

        Returns:
            每只 ETF 计算的指标条数 {"etf_code": count}
        """
        logger.info("开始计算技术指标")

        result = IndicatorService.sync_all_indicators(force_recalc=False)

        total = sum(result.values())
        logger.info(f"技术指标计算完成: {total} 条")

        return result

    @classmethod
    def _generate_signals(
        cls,
        positions: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[SignalModel]:
        """生成交易信号.

        Args:
            positions: 持仓信息

        Returns:
            信号列表
        """
        logger.info("开始生成交易信号")

        signals = SignalService.generate_signals_for_all(positions=positions)

        # 统计信号类型
        buy_count = sum(1 for s in signals if s.signal_type == "BUY")
        sell_count = sum(1 for s in signals if s.signal_type == "SELL")
        hold_count = sum(1 for s in signals if s.signal_type == "HOLD")

        logger.info(f"信号生成完成: 买入={buy_count}, 卖出={sell_count}, 持有={hold_count}")

        return signals

    @classmethod
    def _output_report(
        cls,
        signal_date: date,
        quotes_synced: int,
        indicators_calculated: int,
        signals: List[SignalModel],
        start_time: datetime,
        errors: List[str],
    ) -> Optional[str]:
        """输出日报告.

        Args:
            signal_date: 信号日期
            quotes_synced: 同步的行情数据条数
            indicators_calculated: 计算的指标条数
            signals: 信号列表
            start_time: 开始时间
            errors: 错误列表

        Returns:
            报告文件路径
        """
        try:
            from src.output.reporter import Reporter

            report_path = Reporter.generate_daily_report(
                signal_date=signal_date,
                quotes_synced=quotes_synced,
                indicators_calculated=indicators_calculated,
                signals=signals,
                start_time=start_time,
                end_time=datetime.now(),
                errors=errors,
            )
            return report_path
        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return None


if __name__ == "__main__":
    result = DailyRunner.run(force=True)
    print(f"\n状态: {result.status.value}")
    print(f"信号日期: {result.signal_date}")
    print(f"行情同步: {result.quotes_synced}")
    print(f"指标计算: {result.indicators_calculated}")
    print(f"信号生成: {result.signals_generated}")
    if result.errors:
        print(f"错误: {result.errors}")