"""报告生成器模块.

生成 Markdown 格式的每日交易报告。
"""

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from src.data.models.signal import SignalModel
from src.utils import get_logger


logger = get_logger(__name__)


class Reporter:
    """日报告生成器.

    输出内容：
    - 运行时间和耗时
    - 行情数据同步结果
    - 技术指标计算结果
    - 交易信号汇总（买入/卖出/持有）
    - 风险提示
    """

    # 报告输出目录
    OUTPUT_DIR = Path("reports")

    @classmethod
    def generate_daily_report(
        cls,
        signal_date: date,
        quotes_synced: int,
        indicators_calculated: int,
        signals: List[SignalModel],
        start_time: datetime,
        end_time: datetime,
        errors: List[str],
    ) -> Optional[str]:
        """生成日报告.

        Args:
            signal_date: 信号日期（T-1）
            quotes_synced: 同步的行情数据条数
            indicators_calculated: 计算的指标条数
            signals: 信号列表
            start_time: 开始时间
            end_time: 结束时间
            errors: 错误列表

        Returns:
            报告文件路径

        Example:
            >>> report_path = Reporter.generate_daily_report(
            ...     signal_date=date(2026, 3, 26),
            ...     quotes_synced=5,
            ...     indicators_calculated=5,
            ...     signals=signals,
            ...     start_time=datetime.now(),
            ...     end_time=datetime.now(),
            ...     errors=[],
            ... )
        """
        # 确保输出目录存在
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 生成报告内容
        report_content = cls._build_report_content(
            signal_date=signal_date,
            quotes_synced=quotes_synced,
            indicators_calculated=indicators_calculated,
            signals=signals,
            start_time=start_time,
            end_time=end_time,
            errors=errors,
        )

        # 生成报告文件名
        report_filename = f"daily_report_{signal_date}.md"
        report_path = cls.OUTPUT_DIR / report_filename

        # 写入文件
        try:
            report_path.write_text(report_content, encoding="utf-8")
            logger.info(f"报告已生成: {report_path}")
            return str(report_path)
        except Exception as e:
            logger.error(f"报告写入失败: {e}")
            return None

    @classmethod
    def _build_report_content(
        cls,
        signal_date: date,
        quotes_synced: int,
        indicators_calculated: int,
        signals: List[SignalModel],
        start_time: datetime,
        end_time: datetime,
        errors: List[str],
    ) -> str:
        """构建报告内容.

        Args:
            signal_date: 信号日期
            quotes_synced: 同步的行情数据条数
            indicators_calculated: 计算的指标条数
            signals: 信号列表
            start_time: 开始时间
            end_time: 结束时间
            errors: 错误列表

        Returns:
            Markdown 格式的报告内容
        """
        duration = (end_time - start_time).total_seconds()
        run_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

        # 分类信号
        buy_signals = [s for s in signals if s.signal_type == "BUY"]
        sell_signals = [s for s in signals if s.signal_type == "SELL"]
        hold_signals = [s for s in signals if s.signal_type == "HOLD"]

        # 构建报告
        lines = [
            "# ETF 量化交易信号日报",
            "",
            f"**运行时间**: {run_time_str}",
            f"**信号日期**: {signal_date} (T-1)",
            f"**耗时**: {duration:.1f} 秒",
            "",
            "---",
            "",
            "## 数据同步结果",
            "",
            "| 项目 | 结果 |",
            "|------|------|",
            f"| 行情数据 | {quotes_synced} 条 |",
            f"| 技术指标 | {indicators_calculated} 条 |",
            f"| 信号生成 | {len(signals)} 个 |",
            "",
            "---",
            "",
        ]

        # 买入信号
        lines.extend(cls._format_signal_section("买入信号", buy_signals))

        # 卖出信号
        lines.extend(cls._format_signal_section("卖出信号", sell_signals))

        # 持有信号
        lines.extend(cls._format_hold_section(hold_signals))

        # 错误信息
        if errors:
            lines.extend([
                "---",
                "",
                "## 错误信息",
                "",
            ])
            for error in errors:
                lines.append(f"- {error}")
            lines.append("")

        # 页脚
        lines.extend([
            "---",
            "",
            f"*报告生成时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}*",
        ])

        return "\n".join(lines)

    @classmethod
    def _format_signal_section(
        cls,
        title: str,
        signals: List[SignalModel],
    ) -> List[str]:
        """格式化买入/卖出信号部分.

        Args:
            title: 标题
            signals: 信号列表

        Returns:
            Markdown 行列表
        """
        lines = [
            f"## {title} ({len(signals)})",
            "",
        ]

        if not signals:
            lines.append("无")
            lines.append("")
            return lines

        # 表头
        lines.extend([
            "| ETF代码 | 触发价 | 触发条件 | 建议入场 | 止损价 | 目标价 | 置信度 |",
            "|---------|--------|----------|----------|--------|--------|--------|",
        ])

        for s in signals:
            entry = f"{s.suggested_entry:.3f}" if s.suggested_entry else "-"
            stop = f"{s.stop_loss:.3f}" if s.stop_loss else "-"
            target = f"{s.target_price:.3f}" if s.target_price else "-"
            confidence = f"{s.confidence:.0%}" if s.confidence else "-"
            condition = s.trigger_condition or "-"

            lines.append(
                f"| {s.etf_code} | {s.trigger_price:.3f} | {condition} | "
                f"{entry} | {stop} | {target} | {confidence} |"
            )

        lines.append("")
        return lines

    @classmethod
    def _format_hold_section(
        cls,
        signals: List[SignalModel],
    ) -> List[str]:
        """格式化持有信号部分.

        Args:
            signals: 持有信号列表

        Returns:
            Markdown 行列表
        """
        lines = [
            f"## 持有信号 ({len(signals)})",
            "",
        ]

        if not signals:
            lines.append("无")
            lines.append("")
            return lines

        # 表头
        lines.extend([
            "| ETF代码 | 触发价 | 备注 |",
            "|---------|--------|------|",
        ])

        for s in signals:
            notes = s.notes or "-"
            lines.append(f"| {s.etf_code} | {s.trigger_price:.3f} | {notes} |")

        lines.append("")
        return lines

    @classmethod
    def print_summary(cls, result: "DailyRunResult") -> None:
        """打印执行结果摘要到控制台.

        Args:
            result: 每日运行结果
        """
        print("\n" + "=" * 60)
        print("ETF 量化交易信号日报")
        print("=" * 60)
        print(f"信号日期: {result.signal_date}")
        print(f"运行时间: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"执行状态: {result.status.value}")

        if result.end_time:
            duration = (result.end_time - result.start_time).total_seconds()
            print(f"总耗时: {duration:.1f} 秒")

        print("-" * 60)
        print(f"行情同步: {result.quotes_synced} 条")
        print(f"指标计算: {result.indicators_calculated} 条")
        print(f"信号生成: {result.signals_generated} 个")

        # 分类统计
        buy_count = sum(1 for s in result.signals if s.signal_type == "BUY")
        sell_count = sum(1 for s in result.signals if s.signal_type == "SELL")
        hold_count = sum(1 for s in result.signals if s.signal_type == "HOLD")
        print(f"  - 买入: {buy_count}")
        print(f"  - 卖出: {sell_count}")
        print(f"  - 持有: {hold_count}")

        if result.report_path:
            print("-" * 60)
            print(f"报告路径: {result.report_path}")

        if result.errors:
            print("-" * 60)
            print("错误信息:")
            for error in result.errors:
                print(f"  - {error}")

        print("=" * 60 + "\n")


if __name__ == "__main__":
    # 测试报告生成
    from datetime import date, datetime

    test_signals = [
        SignalModel(
            etf_code="510300",
            signal_type="HOLD",
            trigger_price=3.912,
            notes="MA趋势向上，等待确认",
        ),
    ]

    report_path = Reporter.generate_daily_report(
        signal_date=date(2026, 3, 26),
        quotes_synced=5,
        indicators_calculated=5,
        signals=test_signals,
        start_time=datetime.now(),
        end_time=datetime.now(),
        errors=[],
    )
    print(f"报告生成: {report_path}")