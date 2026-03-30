"""交易信号数据仓库.

提供交易信号的 CRUD 操作。
"""

from typing import List, Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import Signal


class SignalRepository:
    """交易信号仓库类.

    方法均为类方法，直接调用，无需实例化。
    """

    @classmethod
    def create_signal(
        cls,
        db: Session,
        data: Union[dict, Signal],
    ) -> Signal:
        """创建交易信号.

        用于策略判断满足条件后生成信号场景。

        Args:
            db: 数据库会话
            data: 信号数据，支持字典或 Signal 模型实例

        Returns:
            创建的 Signal 实例

        Example:
            >>> with db_session() as db:
            ...     signal = SignalRepository.create_signal(db, {
            ...         "etf_code": "510300",
            ...         "strategy_id": 1,
            ...         "signal_type": "BUY",
            ...         "trigger_price": 3.910,
            ...         "trigger_condition": "MA5>MA20, MACD金叉",
            ...         "suggested_entry": 3.910,
            ...         "stop_loss": 3.600,
            ...         "target_price": 4.500,
            ...         "confidence": 0.85,
            ...     })
        """
        if isinstance(data, Signal):
            new_signal = data
        else:
            new_signal = Signal(**data)

        db.add(new_signal)
        db.flush()
        return new_signal

    @classmethod
    def get_signal_by_id(cls, db: Session, signal_id: int) -> Optional[Signal]:
        """根据 ID 获取信号.

        Args:
            db: 数据库会话
            signal_id: 信号 ID

        Returns:
            Signal 实例，不存在则返回 None

        Example:
            >>> with db_session() as db:
            ...     signal = SignalRepository.get_signal_by_id(db, 1)
        """
        return db.get(Signal, signal_id)

    @classmethod
    def get_active_signals(cls, db: Session) -> List[Signal]:
        """获取当前有效信号列表.

        有效信号状态包括：PENDING（待触发）、ACTIVE（激活中）。
        用于输出报告场景，展示当前建议。

        Args:
            db: 数据库会话

        Returns:
            有效信号列表

        Example:
            >>> with db_session() as db:
            ...     signals = SignalRepository.get_active_signals(db)
            ...     for s in signals:
            ...         print(s.etf_code, s.signal_type, s.signal_status)
        """
        stmt = (
            select(Signal)
            .where(Signal.signal_status.in_(["PENDING", "ACTIVE"]))
            .order_by(Signal.generated_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def update_signal_status(
        cls,
        db: Session,
        signal_id: int,
        new_status: str,
    ) -> Optional[Signal]:
        """更新信号状态.

        用于信号触发、过期、失效等场景。

        Args:
            db: 数据库会话
            signal_id: 信号 ID
            new_status: 新状态（TRIGGERED/EXPIRED/INVALIDATED/ACTIVE）

        Returns:
            更新后的 Signal 实例，不存在则返回 None

        Example:
            >>> with db_session() as db:
            ...     signal = SignalRepository.update_signal_status(
            ...         db, signal_id=1, new_status="TRIGGERED"
            ...     )
        """
        signal = db.get(Signal, signal_id)
        if signal:
            signal.signal_status = new_status
            db.flush()
        return signal