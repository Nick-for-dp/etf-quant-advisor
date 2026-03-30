"""ETF 价格数据仓库.

提供 ETF 日线价格数据的 CRUD 操作。
"""

from datetime import date
from typing import List, Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import ETFQuote


class QuoteRepository:
    """ETF 价格数据仓库类.

    方法均为类方法，直接调用，无需实例化。
    """

    @classmethod
    def upsert_quote(
        cls,
        db: Session,
        data: List[Union[dict, ETFQuote]],
    ) -> List[ETFQuote]:
        """批量新增或更新 ETF 日线价格.

        根据 etf_code + trade_date 判断：存在则更新，不存在则插入。

        Args:
            db: 数据库会话
            data: 价格数据列表，支持字典或 ETFQuote 模型实例

        Returns:
            创建或更新后的 ETFQuote 实例列表

        Example:
            >>> with db_session() as db:
            ...     quotes = QuoteRepository.upsert_quote(db, [
            ...         {"etf_code": "510300", "trade_date": date(2024, 1, 15),
            ...          "open_px": 3.850, "close_px": 3.910},
            ...         {"etf_code": "510500", "trade_date": date(2024, 1, 15),
            ...          "open_px": 5.200, "close_px": 5.350},
            ...     ])
        """
        results: List[ETFQuote] = []

        for item in data:
            # 提取数据
            if isinstance(item, ETFQuote):
                etf_code = item.etf_code
                trade_date = item.trade_date
                values = {
                    "etf_code": item.etf_code,
                    "trade_date": item.trade_date,
                    "open_px": item.open_px,
                    "high_px": item.high_px,
                    "low_px": item.low_px,
                    "close_px": item.close_px,
                    "volume": item.volume,
                    "amount": item.amount,
                    "turnover": item.turnover,
                    "nav": item.nav,
                    "premium_rate": item.premium_rate,
                    "trade_status": item.trade_status,
                }
            else:
                etf_code = item["etf_code"]
                trade_date = item["trade_date"]
                values = item.copy()

            # 查询是否存在（复合主键）
            existing = db.get(ETFQuote, (etf_code, trade_date))
            if existing:
                # 更新已有记录
                for key, value in values.items():
                    if key not in ("etf_code", "trade_date") and hasattr(existing, key):
                        setattr(existing, key, value)
                results.append(existing)
            else:
                # 创建新记录
                new_quote = ETFQuote(**values)
                db.add(new_quote)
                results.append(new_quote)

        db.flush()
        return results

    @classmethod
    def get_recent_quotes(
        cls,
        db: Session,
        etf_code: str,
        limit: int = 60,
    ) -> List[ETFQuote]:
        """获取 ETF 最近 N 日价格数据.

        用于计算技术指标场景（MA60 需要 60 日数据）。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            limit: 返回天数，默认 60 日

        Returns:
            价格列表，按日期升序排列（旧 -> 新）

        Example:
            >>> with db_session() as db:
            ...     quotes = QuoteRepository.get_recent_quotes(db, "510300", 20)
            ...     closes = [q.close_px for q in quotes]
        """
        stmt = (
            select(ETFQuote)
            .where(ETFQuote.etf_code == etf_code)
            .order_by(ETFQuote.trade_date.desc())
            .limit(limit)
        )
        # 按日期升序返回（旧 -> 新），便于计算指标
        results = list(db.execute(stmt).scalars().all())
        return results[::-1]

    @classmethod
    def get_quotes_by_date_range(
        cls,
        db: Session,
        etf_code: str,
        start_date: date,
        end_date: date,
    ) -> List[ETFQuote]:
        """按日期范围获取 ETF 日线价格.

        用于增量更新判断、回测等场景。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            价格列表，按日期升序排列（旧 -> 新）

        Example:
            >>> with db_session() as db:
            ...     quotes = QuoteRepository.get_quotes_by_date_range(
            ...         db, "510300", date(2024, 1, 1), date(2024, 1, 31)
            ...     )
        """
        stmt = (
            select(ETFQuote)
            .where(
                ETFQuote.etf_code == etf_code,
                ETFQuote.trade_date >= start_date,
                ETFQuote.trade_date <= end_date,
            )
            .order_by(ETFQuote.trade_date.asc())
        )
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def get_quotes_by_date(
        cls,
        db: Session,
        trade_date: date,
        etf_codes: Optional[List[str]] = None,
    ) -> List[ETFQuote]:
        """获取指定日期的报价数据.

        用于 Evening Job 获取当日收盘价。

        Args:
            db: 数据库会话
            trade_date: 交易日期
            etf_codes: ETF 代码列表，可选，不传则返回当日所有数据

        Returns:
            ETFQuote 列表

        Example:
            >>> with db_session() as db:
            ...     quotes = QuoteRepository.get_quotes_by_date(
            ...         db, date(2024, 1, 15), ["510300", "512000"]
            ...     )
        """
        stmt = select(ETFQuote).where(ETFQuote.trade_date == trade_date)

        if etf_codes:
            stmt = stmt.where(ETFQuote.etf_code.in_(etf_codes))

        return list(db.execute(stmt).scalars().all())

    @classmethod
    def get_quotes_between(
        cls,
        db: Session,
        etf_codes: List[str],
        start_date: date,
        end_date: date,
    ) -> List[ETFQuote]:
        """批量获取多只 ETF 在日期范围内的报价.

        用于 PerformanceService 批量获取持仓期间价格数据。

        Args:
            db: 数据库会话
            etf_codes: ETF 代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            ETFQuote 列表，按日期升序排列

        Example:
            >>> with db_session() as db:
            ...     quotes = QuoteRepository.get_quotes_between(
            ...         db, ["510300", "512000"], date(2024, 1, 1), date(2024, 1, 31)
            ...     )
        """
        stmt = (
            select(ETFQuote)
            .where(
                ETFQuote.etf_code.in_(etf_codes),
                ETFQuote.trade_date >= start_date,
                ETFQuote.trade_date <= end_date,
            )
            .order_by(ETFQuote.etf_code, ETFQuote.trade_date.asc())
        )
        return list(db.execute(stmt).scalars().all())
