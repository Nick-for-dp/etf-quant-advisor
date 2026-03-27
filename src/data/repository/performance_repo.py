"""信号性能追踪数据仓库.

提供信号性能的 CRUD 操作。
"""

from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import SignalPerformance


class PerformanceRepository:
    """信号性能仓库类.

    方法均为类方法，直接调用，无需实例化。
    """

    @classmethod
    def create_performance(
        cls,
        db: Session,
        data: Union[dict, SignalPerformance],
    ) -> SignalPerformance:
        """创建信号性能追踪记录.

        信号生成时同时创建性能追踪记录，后续每日更新。

        Args:
            db: 数据库会话
            data: 性能数据，支持字典或 SignalPerformance 模型实例

        Returns:
            创建的 SignalPerformance 实例

        Example:
            >>> with db_session() as db:
            ...     perf = PerformanceRepository.create_performance(db, {
            ...         "signal_id": 1,
            ...         "reference_price": 3.910,
            ...     })
        """
        if isinstance(data, SignalPerformance):
            new_perf = data
        else:
            new_perf = SignalPerformance(**data)

        db.add(new_perf)
        db.flush()
        return new_perf

    @classmethod
    def update_performance(
        cls,
        db: Session,
        signal_id: int,
        updates: dict,
    ) -> Optional[SignalPerformance]:
        """更新信号性能数据.

        用于每日收盘后更新收益、极值、回撤等数据。

        Args:
            db: 数据库会话
            signal_id: 关联的信号 ID
            updates: 更新字段字典，如:
                {
                    "return_1d": 0.012,
                    "return_5d": 0.035,
                    "max_price_5d": 4.020,
                    "min_price_5d": 3.900,
                    "max_drawdown_5d": -0.025,
                }

        Returns:
            更新后的 SignalPerformance 实例，不存在则返回 None

        Example:
            >>> with db_session() as db:
            ...     perf = PerformanceRepository.update_performance(
            ...         db, signal_id=1, updates={"return_1d": 0.015}
            ...     )
        """
        stmt = select(SignalPerformance).where(
            SignalPerformance.signal_id == signal_id
        )
        perf = db.execute(stmt).scalar_one_or_none()
        if perf:
            for key, value in updates.items():
                if hasattr(perf, key):
                    setattr(perf, key, value)
            db.flush()
        return perf

    @classmethod
    def get_performance_by_signal(
        cls,
        db: Session,
        signal_id: int,
    ) -> Optional[SignalPerformance]:
        """根据信号 ID 获取性能记录.

        Args:
            db: 数据库会话
            signal_id: 信号 ID

        Returns:
            SignalPerformance 实例，不存在则返回 None

        Example:
            >>> with db_session() as db:
            ...     perf = PerformanceRepository.get_performance_by_signal(db, signal_id=1)
        """
        stmt = select(SignalPerformance).where(
            SignalPerformance.signal_id == signal_id
        )
        return db.execute(stmt).scalar_one_or_none()