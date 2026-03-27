"""数据完整性检查模块.

检查 T-1 交易日数据是否存在、字段是否完整。
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.database import db_session
from src.data.repository.etf_repo import ETFRepository
from src.data.schema import ETFQuote
from src.data.service.trading_calendar_service import TradingCalendarService
from src.utils import get_logger


logger = get_logger(__name__)


@dataclass
class IntegrityCheckResult:
    """完整性检查结果.

    Attributes:
        passed: 检查是否通过
        target_date: 目标日期
        is_trading_day: 是否为交易日
        missing_codes: 缺失数据的 ETF 代码列表
        data_status: 每只 ETF 的数据状态
        warnings: 警告信息列表
        errors: 错误信息列表
    """

    passed: bool
    target_date: Optional[date]
    is_trading_day: bool = False
    missing_codes: List[str] = field(default_factory=list)
    data_status: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class DataIntegrityChecker:
    """数据完整性检查器.

    用于检查 T-1 交易日数据是否完整，包括：
    - 目标日期是否为交易日
    - 所有监控 ETF 的数据是否存在
    - 数据字段是否完整（close_px 不为空等）
    """

    @classmethod
    def check_t1_data(
        cls,
        target_date: Optional[date] = None,
        db: Optional[Session] = None,
    ) -> IntegrityCheckResult:
        """检查 T-1 交易日数据完整性.

        Args:
            target_date: 目标日期，默认为 T-1 交易日
            db: 数据库会话，不传则自动创建

        Returns:
            IntegrityCheckResult: 完整性检查结果

        Example:
            >>> result = DataIntegrityChecker.check_t1_data()
            >>> if result.passed:
            ...     print("数据完整，可以生成信号")
            >>> else:
            ...     print(f"缺失数据: {result.missing_codes}")
        """
        calendar = TradingCalendarService()

        # 1. 确定目标日期
        if target_date is None:
            prev_day_str = calendar.get_previous_trading_day()
            if prev_day_str is None:
                return IntegrityCheckResult(
                    passed=False,
                    target_date=None,
                    is_trading_day=False,
                    errors=["无法获取前一交易日"],
                )
            target_date = date.fromisoformat(prev_day_str)

        # 2. 判断是否为交易日
        is_trading_day = calendar.is_trading_day(target_date)

        if not is_trading_day:
            return IntegrityCheckResult(
                passed=False,
                target_date=target_date,
                is_trading_day=False,
                warnings=[f"{target_date} 不是交易日"],
            )

        # 3. 检查数据
        def _check(session: Session) -> IntegrityCheckResult:
            # 获取所有 ETF 代码
            etfs = ETFRepository.get_all_etfs(session)
            etf_codes = [etf.etf_code for etf in etfs]

            if not etf_codes:
                return IntegrityCheckResult(
                    passed=False,
                    target_date=target_date,
                    is_trading_day=True,
                    errors=["ETF 列表为空"],
                )

            # 查询目标日期的数据
            stmt = select(ETFQuote).where(ETFQuote.trade_date == target_date)
            existing_quotes = session.execute(stmt).scalars().all()
            existing_codes = {q.etf_code for q in existing_quotes}

            # 检查缺失的 ETF
            missing_codes = [code for code in etf_codes if code not in existing_codes]

            # 检查数据字段完整性
            data_status: Dict[str, str] = {}
            warnings: List[str] = []

            for quote in existing_quotes:
                code = quote.etf_code
                if quote.close_px is None:
                    data_status[code] = "invalid: close_px is None"
                    warnings.append(f"{code} 收盘价为空")
                elif quote.trade_status == 0:
                    data_status[code] = "suspended"
                    warnings.append(f"{code} 停牌")
                else:
                    data_status[code] = "ok"

            # 综合判断
            passed = len(missing_codes) == 0 and len(warnings) == 0

            logger.info(
                f"数据完整性检查: target_date={target_date}, "
                f"passed={passed}, missing={len(missing_codes)}, "
                f"warnings={len(warnings)}"
            )

            return IntegrityCheckResult(
                passed=passed,
                target_date=target_date,
                is_trading_day=True,
                missing_codes=missing_codes,
                data_status=data_status,
                warnings=warnings,
            )

        if db is not None:
            return _check(db)
        else:
            with db_session() as session:
                return _check(session)

    @classmethod
    def check_indicator_data(
        cls,
        etf_code: str,
        required_days: int = 5,
        db: Optional[Session] = None,
    ) -> bool:
        """检查指标数据是否足够生成信号.

        策略判断需要至少 2 天的指标数据（MACD 金叉判断）。

        Args:
            etf_code: ETF 代码
            required_days: 需要的指标天数，默认 5 天
            db: 数据库会话

        Returns:
            True 如果指标数据足够

        Example:
            >>> if DataIntegrityChecker.check_indicator_data("510300"):
            ...     print("指标数据足够")
        """
        from src.data.repository.indicator_repo import IndicatorRepository

        def _check(session: Session) -> bool:
            indicators = IndicatorRepository.get_recent_indicators(
                session, etf_code, limit=required_days
            )
            return len(indicators) >= 2  # 至少需要 2 天判断 MACD 金叉

        if db is not None:
            return _check(db)
        else:
            with db_session() as session:
                return _check(session)


if __name__ == "__main__":
    result = DataIntegrityChecker.check_t1_data()
    print(f"检查通过: {result.passed}")
    print(f"目标日期: {result.target_date}")
    print(f"是否交易日: {result.is_trading_day}")
    if result.missing_codes:
        print(f"缺失代码: {result.missing_codes}")
    if result.warnings:
        print(f"警告: {result.warnings}")
    if result.errors:
        print(f"错误: {result.errors}")