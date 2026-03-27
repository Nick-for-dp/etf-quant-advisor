#!/usr/bin/env python
"""ETF 数据初始化脚本.

用于首次部署或重建数据库时的数据初始化。

使用方式：
    # 使用默认日期范围（最近2年）
    python scripts/init_data.py

    # 指定日期范围
    python scripts/init_data.py --start 2024-01-01 --end 2026-03-27

    # 仅初始化 ETF 基础信息
    python scripts/init_data.py --etf-only

    # 强制重新计算所有指标
    python scripts/init_data.py --force-indicators
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database import db_session
from src.data.repository.etf_repo import ETFRepository
from src.data.service.etf_service import ETFService
from src.data.service.indicator_service import IndicatorService
from src.data.service.quote_service import QuoteService
from src.utils import get_logger
from src.utils.config import get_config


logger = get_logger(__name__)


def parse_args():
    """解析命令行参数."""
    parser = argparse.ArgumentParser(
        description="ETF 数据初始化脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/init_data.py                          # 默认最近2年
  python scripts/init_data.py --start 2024-01-01       # 指定开始日期
  python scripts/init_data.py --etf-only               # 仅初始化ETF信息
  python scripts/init_data.py --force-indicators       # 强制重算指标
        """,
    )

    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="开始日期 (YYYY-MM-DD)，默认为2年前",
    )

    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="结束日期 (YYYY-MM-DD)，默认为今天",
    )

    parser.add_argument(
        "--etf-only",
        action="store_true",
        help="仅初始化 ETF 基础信息，不获取行情数据",
    )

    parser.add_argument(
        "--quotes-only",
        action="store_true",
        help="仅同步行情数据（ETF 信息已存在）",
    )

    parser.add_argument(
        "--indicators-only",
        action="store_true",
        help="仅计算技术指标（数据已存在）",
    )

    parser.add_argument(
        "--force-indicators",
        action="store_true",
        help="强制重新计算所有指标（忽略已有数据）",
    )

    parser.add_argument(
        "--skip-etf-info",
        action="store_true",
        help="跳过 ETF 基础信息获取（从配置文件直接写入代码）",
    )

    return parser.parse_args()


def get_date_range(args) -> tuple:
    """获取日期范围.

    Args:
        args: 命令行参数

    Returns:
        (start_date, end_date) 格式为 YYYYMMDD
    """
    # 结束日期
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        end_date = date.today()

    # 开始日期
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        # 默认2年
        start_date = end_date - timedelta(days=730)

    # 转换为 YYYYMMDD 格式
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    return start_str, end_str


def init_etf_info(skip_fetch: bool = False) -> int:
    """初始化 ETF 基础信息.

    Args:
        skip_fetch: 是否跳过网络获取（仅写入代码列表）

    Returns:
        写入的记录数
    """
    print("\n[Step 1] 初始化 ETF 基础信息")
    print("-" * 50)

    codes = ETFService.get_watchlist_codes()
    print(f"配置文件中的 ETF 列表: {len(codes)} 只")

    if skip_fetch:
        # 仅写入代码，不获取详细信息
        from src.data.models.etf import ETFModel

        models = []
        for code in codes:
            models.append(ETFModel(
                etf_code=code,
                etf_name=f"ETF_{code}",  # 占位名称
                market="CN",
            ))

        count = ETFService.save_to_db(models)
        print(f"写入 ETF 代码: {count} 条（跳过详细信息获取）")
        return count

    # 正常获取详细信息
    models = ETFService.sync_watchlist(save_db=True)

    if models:
        print(f"成功获取 ETF 信息: {len(models)} 只")
        for m in models[:5]:
            print(f"  - {m.etf_code}: {m.etf_name} ({m.category or '未知'})")
        if len(models) > 5:
            print(f"  ... 还有 {len(models) - 5} 只")
    else:
        print("警告: 未获取到任何 ETF 信息")

    return len(models)


def init_quotes(start_date: str, end_date: str) -> int:
    """初始化行情数据.

    Args:
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        获取的数据条数
    """
    print(f"\n[Step 2] 同步历史行情数据")
    print("-" * 50)
    print(f"日期范围: {start_date} ~ {end_date}")

    # 获取 ETF 代码列表
    with db_session() as db:
        etfs = ETFRepository.get_all_etfs(db)
        codes = [etf.etf_code for etf in etfs]

    if not codes:
        print("错误: ETF 列表为空，请先运行 --etf-only 初始化 ETF 信息")
        return 0

    print(f"ETF 数量: {len(codes)} 只")

    # 同步数据
    models = QuoteService.sync_daily_quotes(
        start_date=start_date,
        end_date=end_date,
        save_db=True,
    )

    print(f"获取行情数据: {len(models)} 条")

    return len(models)


def init_indicators(force: bool = False) -> dict:
    """计算技术指标.

    Args:
        force: 是否强制重新计算

    Returns:
        每只 ETF 的指标条数
    """
    print(f"\n[Step 3] 计算技术指标")
    print("-" * 50)
    if force:
        print("模式: 强制重新计算所有指标")

    result = IndicatorService.sync_all_indicators(force_recalc=force)

    total = sum(result.values())
    success = sum(1 for v in result.values() if v > 0)

    print(f"计算完成: {success}/{len(result)} 只 ETF")
    print(f"指标数据: {total} 条")

    return result


def print_summary(etf_count: int, quotes_count: int, indicators_result: dict):
    """打印初始化摘要.

    Args:
        etf_count: ETF 数量
        quotes_count: 行情数据条数
        indicators_result: 指标计算结果
    """
    indicators_count = sum(indicators_result.values()) if indicators_result else 0

    print("\n" + "=" * 60)
    print("ETF Quant Advisor - 数据初始化完成")
    print("=" * 60)
    print(f"ETF 数量: {etf_count} 只")
    print(f"行情数据: {quotes_count} 条")
    print(f"指标数据: {indicators_count} 条")
    print("=" * 60)


def main():
    """主入口."""
    args = parse_args()

    print("=" * 60)
    print("ETF Quant Advisor - 数据初始化")
    print("=" * 60)

    start_time = datetime.now()

    # 日期范围
    start_date, end_date = get_date_range(args)
    print(f"时间范围: {start_date} ~ {end_date}")

    etf_count = 0
    quotes_count = 0
    indicators_result = {}

    try:
        # 根据参数决定执行哪些步骤
        if args.indicators_only:
            # 仅计算指标
            indicators_result = init_indicators(args.force_indicators)
            with db_session() as db:
                etfs = ETFRepository.get_all_etfs(db)
                etf_count = len(etfs)

        elif args.quotes_only:
            # 仅同步行情
            quotes_count = init_quotes(start_date, end_date)
            with db_session() as db:
                etfs = ETFRepository.get_all_etfs(db)
                etf_count = len(etfs)

        elif args.etf_only:
            # 仅初始化 ETF 信息
            etf_count = init_etf_info(skip_fetch=args.skip_etf_info)

        else:
            # 完整初始化流程
            # Step 1: ETF 基础信息
            etf_count = init_etf_info(skip_fetch=args.skip_etf_info)

            if etf_count == 0:
                print("\n错误: 未获取到 ETF 信息，初始化终止")
                sys.exit(1)

            # Step 2: 行情数据
            quotes_count = init_quotes(start_date, end_date)

            # Step 3: 技术指标
            indicators_result = init_indicators(args.force_indicators)

        # 打印摘要
        print_summary(etf_count, quotes_count, indicators_result)

        duration = (datetime.now() - start_time).total_seconds()
        print(f"总耗时: {duration:.1f} 秒")

        return 0

    except KeyboardInterrupt:
        print("\n\n用户中断，退出")
        return 1
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        print(f"\n错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())