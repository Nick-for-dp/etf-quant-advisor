"""技术指标数据仓库.

提供 ETF 技术指标的 CRUD 操作。
"""

from datetime import date
from src.data.schema.indicator import ETFIndicator
from typing import List, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import ETFIndicator


class IndicatorRepository:
    """技术指标仓库类.

    方法均为类方法，直接调用，无需实例化。
    """

    @classmethod
    def upsert_indicators(
        cls,
        db: Session,
        data_list: List[Union[dict, ETFIndicator]],
    ) -> int:
        """批量新增或更新技术指标.

        根据 etf_code + trade_date 判断：存在则更新，不存在则插入。
        用于指标计算完成后保存场景。

        Args:
            db: 数据库会话
            data_list: 指标数据列表，支持字典或 ETFIndicator 模型实例

        Returns:
            处理的记录条数

        Example:
            >>> with db_session() as db:
            ...     count = IndicatorRepository.upsert_indicators(db, [
            ...         {
            ...             "etf_code": "510300",
            ...             "trade_date": date(2024, 1, 15),
            ...             "ma5": 3.890,
            ...             "ma20": 3.850,
            ...             "macd_dif": 0.012,
            ...             "macd_dea": 0.008,
            ...             "rsi_6": 55.5,
            ...         },
            ...         {
            ...             "etf_code": "510500",
            ...             "trade_date": date(2024, 1, 15),
            ...             "ma5": 5.120,
            ...             "ma20": 5.080,
            ...         },
            ...     ])
        """
        for data in data_list:
            # 提取数据
            if isinstance(data, ETFIndicator):
                etf_code = data.etf_code
                trade_date = data.trade_date
                values = {
                    "etf_code": etf_code,
                    "trade_date": trade_date,
                    "ma5": data.ma5,
                    "ma10": data.ma10,
                    "ma20": data.ma20,
                    "ma60": data.ma60,
                    "macd_dif": data.macd_dif,
                    "macd_dea": data.macd_dea,
                    "macd_bar": data.macd_bar,
                    "rsi_6": data.rsi_6,
                    "rsi_12": data.rsi_12,
                    "rsi_24": data.rsi_24,
                    "boll_upper": data.boll_upper,
                    "boll_mid": data.boll_mid,
                    "boll_lower": data.boll_lower,
                    "atr_14": data.atr_14,
                    "adx": data.adx,
                    "adx_plus_di": data.adx_plus_di,
                    "adx_minus_di": data.adx_minus_di,
                    "volume_ma5": data.volume_ma5,
                    "volume_ma20": data.volume_ma20,
                    "volume_ratio": data.volume_ratio,
                }
            else:
                etf_code = data["etf_code"]
                trade_date = data["trade_date"]
                values = data.copy()

            # 查询是否存在（复合主键）
            stmt = select(ETFIndicator).where(
                ETFIndicator.etf_code == etf_code,
                ETFIndicator.trade_date == trade_date,
            )
            existing = db.execute(stmt).scalar_one_or_none()

            if existing:
                # 更新已有记录
                for key, value in values.items():
                    if key not in ("etf_code", "trade_date") and hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                # 创建新记录
                new_indicator = ETFIndicator(**values)
                db.add(new_indicator)

        db.flush()
        return len(data_list)

    @classmethod
    def get_recent_indicators(
        cls,
        db: Session,
        etf_code: str,
        limit: int = 20,
    ) -> List[ETFIndicator]:
        """获取 ETF 最近 N 日技术指标.

        用于信号判断场景，查看历史趋势。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            limit: 返回天数，默认 20 日

        Returns:
            指标列表，按日期升序排列（旧 -> 新）

        Example:
            >>> with db_session() as db:
            ...     indicators = IndicatorRepository.get_recent_indicators(db, "510300")
            ...     latest = indicators[-1]  # 最新一日
        """
        stmt = (
            select(ETFIndicator)
            .where(ETFIndicator.etf_code == etf_code)
            .order_by(ETFIndicator.trade_date.desc())
            .limit(limit)
        )
        results = list[ETFIndicator](db.execute(stmt).scalars().all())
        return results[::-1]

    @classmethod
    def get_indicators_by_date_range(
        cls,
        db: Session,
        etf_code: str,
        start_date: date,
        end_date: date,
    ) -> List[ETFIndicator]:
        """按日期范围获取技术指标.

        用于增量更新判断、回测等场景。

        Args:
            db: 数据库会话
            etf_code: ETF 代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            指标列表，按日期升序排列（旧 -> 新）

        Example:
            >>> with db_session() as db:
            ...     indicators = IndicatorRepository.get_indicators_by_date_range(
            ...         db, "510300", date(2024, 1, 1), date(2024, 1, 31)
            ...     )
        """
        stmt = (
            select(ETFIndicator)
            .where(
                ETFIndicator.etf_code == etf_code,
                ETFIndicator.trade_date >= start_date,
                ETFIndicator.trade_date <= end_date,
            )
            .order_by(ETFIndicator.trade_date.asc())
        )
        return list[ETFIndicator](db.execute(stmt).scalars().all())
