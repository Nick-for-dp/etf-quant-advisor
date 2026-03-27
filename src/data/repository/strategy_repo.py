"""策略配置数据仓库.

提供策略配置的查询操作。
策略配置为系统内置，运行期间只读。
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import Strategy


class StrategyRepository:
    """策略配置仓库类.

    方法均为类方法，直接调用，无需实例化。
    """

    @classmethod
    def get_active_strategies(cls, db: Session) -> List[Strategy]:
        """获取所有激活的策略列表.

        用于信号生成场景，遍历策略判断买卖条件。

        Args:
            db: 数据库会话

        Returns:
            激活状态的策略列表

        Example:
            >>> with db_session() as db:
            ...     strategies = StrategyRepository.get_active_strategies(db)
            ...     for s in strategies:
            ...         print(s.strategy_name, s.strategy_type)
        """
        stmt = (
            select(Strategy)
            .where(Strategy.is_active == True)
            .order_by(Strategy.id)
        )
        return list(db.execute(stmt).scalars().all())