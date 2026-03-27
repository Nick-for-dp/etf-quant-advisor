"""技术指标计算服务.

负责协调价格数据和指标数据的增量更新判断，以及指标计算和保存。

数据策略：
    - 停牌日（trade_status=0）不存储指标数据
    - 查询指标时自动只返回交易日指标
    - 策略层应通过本服务获取指标，不应直接调用 Repository
"""

from datetime import date, timedelta
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from src.analysis import calculate_all_indicators
from src.data.database import db_session
from src.data.models.indicator import IndicatorModel
from src.data.models.quote import QuoteModel
from src.data.repository.etf_repo import ETFRepository
from src.data.repository.indicator_repo import IndicatorRepository
from src.data.repository.quote_repo import QuoteRepository
from src.utils import get_logger

logger = get_logger(__name__)

# 指标计算所需的最小数据天数（MA60 需要60天）
MIN_DATA_DAYS = 60

# 策略判断所需的指标天数（MACD金叉需要前一日数据，预留缓冲）
INDICATOR_DAYS_FOR_SIGNAL = 5


class IndicatorService:
    """技术指标计算服务类.

    提供指标数据的增量更新和计算功能。
    """

    @classmethod
    def get_missing_dates(
        cls,
        db: Session,
        etf_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[date]:
        """获取需要计算指标的日期列表.

        对比价格数据和指标数据，返回缺失指标的日期。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            start_date: 开始日期，默认为价格数据最早日期
            end_date: 结束日期，默认为今天

        Returns:
            需要计算指标的日期列表，按日期升序排列

        Example:
            >>> with db_session() as db:
            ...     dates = IndicatorService.get_missing_dates(db, "510300")
            ...     print(f"需要计算 {len(dates)} 天的指标")
        """
        # 默认结束日期为今天
        if end_date is None:
            end_date = date.today()

        # 获取价格数据的日期范围
        quotes = QuoteRepository.get_quotes_by_date_range(
            db, etf_code,
            start_date or date(2026, 1, 1),  # 默认从2026年开始
            end_date
        )

        if not quotes:
            logger.warning(f"ETF {etf_code} 无价格数据")
            return []

        # 价格数据日期集合
        quote_dates: Set[date] = {q.trade_date for q in quotes}

        # 实际价格数据的日期范围
        actual_start = min(quote_dates)
        actual_end = max(quote_dates)

        # 获取已有指标的日期
        indicators = IndicatorRepository.get_indicators_by_date_range(
            db, etf_code, actual_start, actual_end
        )
        indicator_dates: Set[date] = {ind.trade_date for ind in indicators}

        # 计算差集
        missing_dates = quote_dates - indicator_dates

        logger.debug(
            f"ETF {etf_code}: 价格数据 {len(quote_dates)} 天, "
            f"指标数据 {len(indicator_dates)} 天, "
            f"缺失 {len(missing_dates)} 天"
        )

        return sorted(missing_dates)

    @classmethod
    def calculate_indicators(
        cls,
        quotes: List[QuoteModel],
    ) -> List[IndicatorModel]:
        """根据价格数据计算技术指标.

        数据合法性检查：
        - 价格数据不能为空
        - 数据天数不少于 MIN_DATA_DAYS（60天）
        - 必须包含 close_px、high_px、low_px、volume 字段
        - 数据需按日期升序排列

        Args:
            quotes: 价格数据列表，按日期升序排列

        Returns:
            指标数据列表（IndicatorModel 格式，可直接用于 save_to_db）

        Example:
            >>> quotes = QuoteRepository.get_recent_quotes(db, "510300", limit=60)
            >>> quote_models = [QuoteModel.from_schema(q) for q in quotes]
            >>> indicators = IndicatorService.calculate_indicators(quote_models)
        """
        # 1. 空数据检查
        if not quotes:
            logger.warning("价格数据为空，无法计算指标")
            return []

        # 2. 数据量检查
        if len(quotes) < MIN_DATA_DAYS:
            logger.warning(
                f"价格数据不足 {MIN_DATA_DAYS} 天（当前 {len(quotes)} 天），"
                f"部分指标将无法计算"
            )

        # 3. 数据完整性检查：关键字段不能为空
        for i, q in enumerate(quotes):
            if q.close_px is None:
                logger.warning(f"第 {i} 条数据 close_px 为空，跳过计算")
                return []
            if q.high_px is None or q.low_px is None:
                logger.warning(f"第 {i} 条数据 high_px 或 low_px 为空，跳过计算")
                return []

        # 4. 调用 analysis 模块计算指标
        logger.info(f"开始计算 {len(quotes)} 天的技术指标")
        indicators = calculate_all_indicators(quotes)

        logger.info(f"指标计算完成，生成 {len(indicators)} 条指标数据")
        return indicators

    @classmethod
    def save_to_db(
        cls,
        models: List[IndicatorModel],
        db: Optional[Session] = None,
    ) -> int:
        """将指标数据批量写入数据库.

        Args:
            models: IndicatorModel 列表
            db: 数据库会话，不传则自动创建

        Returns:
            成功写入的记录数
        """
        if not models:
            logger.warning("无指标数据需要写入")
            return 0

        # 转换为 ORM Schema 列表
        schemas = [model.to_schema() for model in models]

        def _save(session: Session) -> int:
            return IndicatorRepository.upsert_indicators(session, schemas)

        # 判断是否需要自动管理会话
        if db is not None:
            count = _save(db)
        else:
            with db_session() as session:
                count = _save(session)

        logger.info(f"成功写入 {count} 条指标记录到数据库")
        return count

    @classmethod
    def sync_indicators_for_etf(
        cls,
        db: Session,
        etf_code: str,
        force_recalc: bool = False,
    ) -> int:
        """同步单个 ETF 的技术指标.

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            force_recalc: 是否强制重新计算所有指标

        Returns:
            计算并保存的指标条数

        Example:
            >>> with db_session() as db:
            ...     count = IndicatorService.sync_indicators_for_etf(db, "510300")
            ...     print(f"计算并保存 {count} 条指标")
        """
        logger.info(f"开始同步 ETF {etf_code} 的技术指标")

        # 1. 判断需要计算的日期
        if force_recalc:
            # 强制重新计算：获取所有价格数据
            quotes = QuoteRepository.get_recent_quotes(db, etf_code, limit=1000)
            missing_dates = None  # 标记为全量计算
        else:
            # 增量计算：只计算缺失的日期
            missing_dates = cls.get_missing_dates(db, etf_code)

            if not missing_dates:
                logger.info(f"ETF {etf_code} 指标数据已是最新，无需计算")
                return 0

            # 获取计算指标所需的价格数据
            # MA60 需要60天历史数据，预留90天缓冲
            start_date = min(missing_dates) - timedelta(days=90)
            end_date = max(missing_dates)
            quotes = QuoteRepository.get_quotes_by_date_range(
                db, etf_code, start_date, end_date
            )

        # 2. 价格数据检查
        if not quotes:
            logger.warning(f"ETF {etf_code} 无价格数据，跳过指标计算")
            return 0

        if len(quotes) < MIN_DATA_DAYS:
            logger.warning(
                f"ETF {etf_code} 价格数据仅 {len(quotes)} 天，"
                f"少于 {MIN_DATA_DAYS} 天，部分指标无法计算"
            )

        # 3. 转换为业务模型
        quote_models = [QuoteModel.from_schema(q) for q in quotes]

        # 4. 计算指标
        indicator_models = cls.calculate_indicators(quote_models)

        if not indicator_models:
            logger.warning(f"ETF {etf_code} 指标计算失败或无结果")
            return 0

        # 5. 过滤：增量模式下只保存缺失日期的指标
        if missing_dates is not None:
            missing_dates_set = set(missing_dates)
            indicator_models = [
                m for m in indicator_models
                if m.get_trade_date() in missing_dates_set
            ]

        # 6. 保存到数据库
        count = cls.save_to_db(indicator_models, db)

        logger.info(f"ETF {etf_code} 指标同步完成，保存 {count} 条记录")
        return count

    @classmethod
    def sync_all_indicators(
        cls,
        force_recalc: bool = False,
    ) -> dict:
        """同步所有 ETF 的技术指标（主入口）.

        Args:
            force_recalc: 是否强制重新计算所有指标

        Returns:
            同步结果统计 {"etf_code": count, ...}

        Example:
            >>> result = IndicatorService.sync_all_indicators()
            >>> for etf_code, count in result.items():
            ...     print(f"{etf_code}: {count} 条")
        """
        logger.info("开始同步所有 ETF 的技术指标")

        with db_session() as db:
            # 1. 获取所有 ETF 代码
            etfs = ETFRepository.get_all_etfs(db)
            if not etfs:
                logger.warning("ETF 列表为空，无数据需要同步")
                return {}

            # 2. 逐个 ETF 同步指标
            results = {}
            for etf in etfs:
                try:
                    count = cls.sync_indicators_for_etf(db, etf.etf_code, force_recalc)
                    results[etf.etf_code] = count
                except Exception as e:
                    logger.error(f"ETF {etf.etf_code} 指标同步失败: {e}")
                    results[etf.etf_code] = 0

        total = sum(results.values())
        logger.info(f"指标同步完成，共处理 {len(results)} 只 ETF，保存 {total} 条记录")
        return results

    # ==================== 策略层查询接口 ====================

    @classmethod
    def get_recent_indicators(
        cls,
        db: Session,
        etf_code: str,
        limit: int = INDICATOR_DAYS_FOR_SIGNAL,
    ) -> List[IndicatorModel]:
        """获取 ETF 最近 N 个交易日的指标数据.

        这是策略层获取指标的主要接口。

        重要说明：
            - 由于停牌日不存储指标，返回的自然是最近 N 个交易日
            - 返回结果按日期升序排列（旧 -> 新），便于判断趋势变化
            - 用于策略判断时，indicators[-1] 是最新交易日指标

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            limit: 返回天数，默认 5 天（足以判断 MACD 金叉等条件）

        Returns:
            指标数据列表，按日期升序排列（旧 -> 新）

        Example:
            >>> with db_session() as db:
            ...     indicators = IndicatorService.get_recent_indicators(db, "510300")
            ...     latest = indicators[-1]  # 最新交易日
            ...     prev = indicators[-2]    # 前一交易日（用于判断金叉）
            ...     # 判断 MACD 金叉
            ...     is_golden_cross = (
            ...         latest.macd_dif > latest.macd_dea and
            ...         prev.macd_dif < prev.macd_dea
            ...     )
        """
        indicators = IndicatorRepository.get_recent_indicators(db, etf_code, limit)

        # 转换为业务模型
        models = [IndicatorModel.from_schema(ind) for ind in indicators]

        logger.debug(f"获取 ETF {etf_code} 最近 {len(models)} 个交易日指标")
        return models

    @classmethod
    def get_indicator_by_date(
        cls,
        db: Session,
        etf_code: str,
        target_date: date,
    ) -> Optional[IndicatorModel]:
        """获取指定日期的指标数据.

        用于回测或特定日期分析。

        注意：如果 target_date 是停牌日，返回 None。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            target_date: 目标日期

        Returns:
            指标数据，如果日期是停牌日或不存在则返回 None

        Example:
            >>> with db_session() as db:
            ...     indicator = IndicatorService.get_indicator_by_date(
            ...         db, "510300", date(2024, 1, 15)
            ...     )
            ...     if indicator:
            ...         print(f"MA20: {indicator.ma20}")
        """
        indicators = IndicatorRepository.get_indicators_by_date_range(
            db, etf_code, target_date, target_date
        )

        if not indicators:
            logger.debug(f"ETF {etf_code} 在 {target_date} 无指标数据（可能是停牌日）")
            return None

        return IndicatorModel.from_schema(indicators[0])


if __name__ == "__main__":
    IndicatorService.sync_all_indicators(force_recalc=True)
