"""ETF 日线数据服务.

负责整合数据获取、模型转换、数据库写入的业务流程编排。

数据策略：
    - 停牌日填充数据：价格=前一日收盘，volume=0，trade_status=0
    - 策略层应通过本服务获取价格数据，不应直接调用 Repository
"""

from datetime import date
from datetime import datetime as dt
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from src.data.database import db_session
from src.data.models.quote import QuoteModel
from src.data.repository.etf_repo import ETFRepository
from src.data.repository.quote_repo import QuoteRepository
from src.data.source.akshare_client import build_quote_data_hybrid
from src.data.service.trading_calendar_service import TradingCalendarService
from src.utils import get_logger


logger = get_logger(__name__)


class QuoteService:
    """ETF 日线数据服务类.

    提供日线数据的同步功能。
    """

    @classmethod
    def get_etf_codes(cls, db: Optional[Session] = None) -> List[str]:
        """从数据库获取所有 ETF 代码.

        Args:
            db: 数据库会话，不传则自动创建

        Returns:
            ETF 代码列表

        Example:
            >>> codes = QuoteService.get_etf_codes()
            >>> print(codes)
            ['510300', '512000', '513100']
        """
        def _fetch(session: Session) -> List[str]:
            etfs = ETFRepository.get_all_etfs(session)
            return [etf.etf_code for etf in etfs]

        if db is not None:
            codes = _fetch(db)
        else:
            with db_session() as session:
                codes = _fetch(session)

        logger.info(f"从数据库获取到 {len(codes)} 个 ETF 代码")
        return codes

    @classmethod
    def fetch_daily_quotes(
        cls,
        codes: List[str],
        start_date: str,
        end_date: str,
    ) -> List[QuoteModel]:
        """批量获取 ETF 日线数据并转换为业务模型.

        Args:
            codes: ETF 代码列表
            start_date: 开始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"

        Returns:
            QuoteModel 列表（仅包含成功获取的数据）

        Example:
            >>> models = QuoteService.fetch_daily_quotes(['510300', '510500'], '20240101', '20240131')
            >>> for model in models:
            ...     print(model.etf_code, model.trade_date, model.close_px)
        """
        models: List[QuoteModel] = []

        for code in codes:
            quotes = build_quote_data_hybrid(code, start_date, end_date)
            if quotes is None:
                logger.warning(f"获取 ETF {code} 日线数据失败，跳过")
                continue
            models.extend(quotes)
            logger.debug(f"成功获取 ETF {code} 日线数据 {len(quotes)} 条")

        logger.info(f"成功获取 {len(models)} 条日线数据")
        return models

    @classmethod
    def save_to_db(cls, models: List[QuoteModel], db: Optional[Session] = None) -> int:
        """将日线数据批量写入数据库.

        Args:
            models: QuoteModel 列表
            db: 数据库会话，不传则自动创建

        Returns:
            成功写入的记录数

        Example:
            >>> models = QuoteService.fetch_daily_quotes(['510300'], '20240101', '20240131')
            >>> count = QuoteService.save_to_db(models)
            >>> print(f"写入 {count} 条记录")
        """
        if not models:
            logger.warning("无日线数据需要写入")
            return 0

        # 转换为 ORM Schema 列表
        schemas = [model.to_schema() for model in models]

        def _save(session: Session) -> int:
            QuoteRepository.upsert_quote(session, schemas)
            return len(schemas)

        # 判断是否需要自动管理会话
        if db is not None:
            count = _save(db)
        else:
            with db_session() as session:
                count = _save(session)

        logger.info(f"成功写入 {count} 条日线记录到数据库")
        return count

    @classmethod
    def sync_daily_quotes(
        cls,
        start_date: str,
        end_date: str,
        save_db: bool = True,
    ) -> List[QuoteModel]:
        """同步日线数据（主入口）.

        整合数据获取、模型转换、数据库写入的完整流程。

        Args:
            start_date: 开始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
            save_db: 是否写入数据库，默认 True

        Returns:
            QuoteModel 列表

        Example:
            >>> models = QuoteService.sync_daily_quotes('20240101', '20240131')
            >>> print(f"获取 {len(models)} 条日线数据")
        """
        logger.info(f"开始同步日线数据: {start_date} ~ {end_date}")

        # 1. 获取 ETF 代码列表
        codes = cls.get_etf_codes()
        if not codes:
            logger.warning("ETF 列表为空，无数据需要同步")
            return []

        # 2. 批量获取日线数据
        models = cls.fetch_daily_quotes(codes, start_date, end_date)

        # 3. 写入数据库
        if save_db and models:
            cls.save_to_db(models)

        logger.info(f"同步完成，共获取 {len(models)} 条日线数据")
        return models

    @classmethod
    def sync_single_day(
        cls,
        target_date: Optional[Union[str, date]] = None,
        save_db: bool = True,
    ) -> Dict[str, Any]:
        """同步单日ETF行情数据（便捷方法）.

        用于日常增量更新场景，自动获取 T-1 交易日数据。

        Args:
            target_date: 目标日期，默认为 T-1 交易日
                         支持格式："YYYY-MM-DD"、"YYYYMMDD"、date 对象
            save_db: 是否写入数据库，默认 True

        Returns:
            {
                "target_date": "2026-03-26",
                "is_trading_day": True,
                "quotes_count": 5,
                "duration_seconds": 60.5,
                "status": "success",
                "errors": []
            }

        Example:
            >>> result = QuoteService.sync_single_day()  # 默认 T-1
            >>> result = QuoteService.sync_single_day("2026-03-20")
        """
        start_time = dt.now()
        errors: List[str] = []

        # 1. 获取目标日期
        calendar = TradingCalendarService()

        if target_date is None:
            # 默认获取 T-1 交易日
            target_date_str = calendar.get_previous_trading_day()
            if target_date_str is None:
                return {
                    "target_date": None,
                    "is_trading_day": False,
                    "quotes_count": 0,
                    "duration_seconds": 0.0,
                    "status": "error",
                    "errors": ["无法获取前一交易日"],
                }
            target_date = target_date_str

        # 2. 统一日期格式
        if isinstance(target_date, date):
            target_date_fmt = target_date.strftime("%Y-%m-%d")
            target_date_ymd = target_date.strftime("%Y%m%d")
        elif isinstance(target_date, str):
            if "-" in target_date:
                target_date_fmt = target_date
                target_date_ymd = target_date.replace("-", "")
            else:
                target_date_fmt = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}"
                target_date_ymd = target_date
        else:
            return {
                "target_date": str(target_date),
                "is_trading_day": False,
                "quotes_count": 0,
                "duration_seconds": 0.0,
                "status": "error",
                "errors": [f"不支持的日期格式: {type(target_date)}"],
            }

        logger.info(f"开始同步单日数据: {target_date_fmt}")

        # 3. 判断是否为交易日
        is_trading_day = calendar.is_trading_day(target_date_fmt)

        if not is_trading_day:
            logger.info(f"{target_date_fmt} 不是交易日，跳过数据同步")
            return {
                "target_date": target_date_fmt,
                "is_trading_day": False,
                "quotes_count": 0,
                "duration_seconds": (dt.now() - start_time).total_seconds(),
                "status": "skipped",
                "errors": [],
            }

        # 4. 同步数据
        try:
            models = cls.sync_daily_quotes(
                start_date=target_date_ymd,
                end_date=target_date_ymd,
                save_db=save_db,
            )

            duration = (dt.now() - start_time).total_seconds()
            logger.info(f"单日同步完成: {target_date_fmt}, {len(models)} 条数据, 耗时 {duration:.1f} 秒")

            return {
                "target_date": target_date_fmt,
                "is_trading_day": True,
                "quotes_count": len(models),
                "duration_seconds": duration,
                "status": "success",
                "errors": errors,
            }

        except Exception as e:
            error_msg = f"数据同步失败: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

            return {
                "target_date": target_date_fmt,
                "is_trading_day": True,
                "quotes_count": 0,
                "duration_seconds": (dt.now() - start_time).total_seconds(),
                "status": "error",
                "errors": errors,
            }

    # ==================== 策略层查询接口 ====================

    @classmethod
    def get_latest_quote(
        cls,
        db: Session,
        etf_code: str,
    ) -> Optional[QuoteModel]:
        """获取 ETF 最新一天的价格数据.

        这是策略层获取价格的主要接口。

        重要说明：
            - 返回最新一天的数据，可能是交易日或停牌日
            - 策略层需要检查 trade_status 判断是否为停牌日
            - trade_status=1 表示正常交易，trade_status=0 表示停牌

        Args:
            db: 数据库会话
            etf_code: ETF 代码

        Returns:
            最新价格数据，不存在则返回 None

        Example:
            >>> with db_session() as db:
            ...     quote = QuoteService.get_latest_quote(db, "510300")
            ...     if quote and quote.trade_status == 1:
            ...         print(f"收盘价: {quote.close_px}, 溢价率: {quote.premium_rate}")
        """
        quotes = QuoteRepository.get_recent_quotes(db, etf_code, limit=1)

        if not quotes:
            logger.debug(f"ETF {etf_code} 无价格数据")
            return None

        model = QuoteModel.from_schema(quotes[0])
        logger.debug(
            f"获取 ETF {etf_code} 最新价格: {model.trade_date}, "
            f"trade_status={model.trade_status}"
        )
        return model

    @classmethod
    def get_recent_quotes(
        cls,
        db: Session,
        etf_code: str,
        limit: int = 20,
    ) -> List[QuoteModel]:
        """获取 ETF 最近 N 天的价格数据.

        用于策略判断或技术指标计算。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            limit: 返回天数，默认 20 天

        Returns:
            价格数据列表，按日期升序排列（旧 -> 新）

        Example:
            >>> with db_session() as db:
            ...     quotes = QuoteService.get_recent_quotes(db, "510300", 5)
            ...     # 过滤停牌日，只看交易日
            ...     trading_quotes = [q for q in quotes if q.trade_status == 1]
        """
        quotes = QuoteRepository.get_recent_quotes(db, etf_code, limit)
        models = [QuoteModel.from_schema(q) for q in quotes]

        logger.debug(f"获取 ETF {etf_code} 最近 {len(models)} 天价格数据")
        return models

    @classmethod
    def get_quote_by_date(
        cls,
        db: Session,
        etf_code: str,
        target_date: date,
    ) -> Optional[QuoteModel]:
        """获取指定日期的价格数据.

        用于回测或特定日期分析。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            target_date: 目标日期

        Returns:
            价格数据，不存在则返回 None

        Example:
            >>> with db_session() as db:
            ...     quote = QuoteService.get_quote_by_date(
            ...         db, "510300", date(2024, 1, 15)
            ...     )
        """
        quotes = QuoteRepository.get_quotes_by_date_range(
            db, etf_code, target_date, target_date
        )

        if not quotes:
            logger.debug(f"ETF {etf_code} 在 {target_date} 无价格数据")
            return None

        return QuoteModel.from_schema(quotes[0])


if __name__ == "__main__":
    start_date = "20260310"
    end_date = "20260325"

    models = QuoteService.sync_daily_quotes(start_date, end_date)
    print(f"获取 {len(models)} 条日线数据")
