#!/usr/bin/env python
r"""ETF 量化交易顾问系统主入口.

提供每日运行流程的命令行入口，支持外部调度工具调用。

使用方式：
    # Morning Job（开盘前，生成信号）
    python main.py --morning
    python main.py --morning --force   # 强制执行

    # Evening Job（收盘后，更新性能追踪）
    python main.py --evening
    python main.py --evening --force   # 强制执行

    # 兼容旧版（等同于 --morning）
    python main.py --run-now

外部调度示例（Windows Task Scheduler）：
    # 每日 08:00 执行 Morning Job
    python D:\projects\etf_quant_advisor\main.py --morning

    # 每日 15:30 执行 Evening Job
    python D:\projects\etf_quant_advisor\main.py --evening
"""

import argparse
import sys
from datetime import date

from src.core import DailyRunner, RunStatus
from src.core.evening_runner import EveningRunner, EveningStatus
from src.output.reporter import Reporter
from src.utils import get_logger


logger = get_logger(__name__)


def main():
    """主入口函数."""
    parser = argparse.ArgumentParser(
        description="ETF 量化交易顾问系统 - 每日生成交易信号与性能追踪",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Morning Job（开盘前）
  python main.py --morning           # 生成信号
  python main.py --morning --force   # 强制执行

  # Evening Job（收盘后）
  python main.py --evening           # 更新性能追踪
  python main.py --evening --force   # 强制执行

  # 兼容旧版
  python main.py --run-now           # 等同于 --morning

外部调度（Windows Task Scheduler）:
  # 每日 08:00 执行 Morning Job
  python D:\\projects\\etf_quant_advisor\\main.py --morning

  # 每日 15:30 执行 Evening Job
  python D:\\projects\\etf_quant_advisor\\main.py --evening

报告输出:
  - 控制台: 实时显示执行进度和结果摘要
  - Markdown 文件: reports/daily_report_YYYY-MM-DD.md
        """,
    )

    # 运行模式参数
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--morning",
        action="store_true",
        help="开盘前任务（生成信号）",
    )
    mode_group.add_argument(
        "--evening",
        action="store_true",
        help="收盘后任务（更新性能追踪）",
    )
    mode_group.add_argument(
        "--run-now",
        action="store_true",
        help="[兼容旧版] 等同于 --morning",
    )

    # 可选参数
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行，忽略时间检查和非交易日检查",
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="指定目标日期（格式: YYYY-MM-DD），默认为 T-1 交易日",
    )

    parser.add_argument(
        "--no-report",
        action="store_true",
        help="不生成日报告文件",
    )

    args = parser.parse_args()

    # 检查是否指定了运行模式
    if not (args.morning or args.evening or args.run_now):
        parser.print_help()
        sys.exit(0)

    try:
        # 解析目标日期
        target_date = None
        if args.date:
            try:
                target_date = date.fromisoformat(args.date)
            except ValueError:
                print(f"错误: 无效的日期格式 '{args.date}'，请使用 YYYY-MM-DD 格式")
                sys.exit(1)

        # Evening Job
        if args.evening:
            logger.info("启动 Evening Job（收盘后性能追踪）")
            result = EveningRunner.run(force=args.force)
            Reporter.print_evening_summary(result)

            if result.status == EveningStatus.SUCCESS:
                sys.exit(0)
            elif result.status == EveningStatus.SKIPPED:
                sys.exit(0)
            else:
                sys.exit(1)

        # Morning Job（或 --run-now 兼容旧版）
        logger.info("启动 Morning Job（开盘前信号生成）")

        result = DailyRunner.run(
            force=args.force,
            output_report=not args.no_report,
            target_date=target_date,
        )

        # 打印结果摘要
        Reporter.print_summary(result)

        # 返回退出码
        if result.status == RunStatus.SUCCESS:
            sys.exit(0)
        elif result.status == RunStatus.SKIPPED:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("收到中断信号，程序退出")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()