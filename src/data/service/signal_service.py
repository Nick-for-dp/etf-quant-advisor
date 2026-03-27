"""交易信号生成服务.

负责整合指标数据、价格数据、策略判断，生成并持久化交易信号。

使用流程：
    1. 获取ETF列表
    2. 获取指标数据和价格数据
    3. 调用策略判断买入/卖出条件
    4. 生成SignalModel
    5. 持久化到数据库
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from src.data.database import db_session
from src.data.models.indicator import IndicatorModel
from src.data.models.quote import QuoteModel
from src.data.models.signal import SignalModel
from src.data.repository.etf_repo import ETFRepository
from src.data.repository.quote_repo import QuoteRepository
from src.data.repository.signal_repo import SignalRepository
from src.data.service.indicator_service import IndicatorService
from src.data.service.quote_service import QuoteService
from src.strategy.right_side import (
    generate_buy_signal,
    generate_sell_signal,
    generate_hold_signal,
    check_buy_signal,
    check_sell_signal,
    BuySignalCheck,
    SellSignalCheck,
)
from src.utils import get_logger


logger = get_logger(__name__)


class SignalService:
    """交易信号生成服务.

    提供信号生成和持久化功能。
    """

    # 策略ID映射（后续可从数据库读取）
    STRATEGY_ID_RIGHT_SIDE = 1

    @classmethod
    def generate_signal_for_etf(
        cls,
        db: Session,
        etf_code: str,
        strategy_id: Optional[int] = None,
        entry_price: Optional[Decimal] = None,
        highest_price: Optional[Decimal] = None,
    ) -> Optional[SignalModel]:
        """为单个ETF生成交易信号.

        Args:
            db: 数据库会话
            etf_code: ETF代码
            strategy_id: 策略ID，默认使用右侧交易策略
            entry_price: 持仓成本价（用于卖出判断）
            highest_price: 持仓期间最高价（用于移动止盈）

        Returns:
            SignalModel 或 None

        Example:
            >>> with db_session() as db:
            ...     signal = SignalService.generate_signal_for_etf(db, "510300")
            ...     if signal:
            ...         print(f"{signal.signal_type}: {signal.trigger_condition}")
        """
        strategy_id = strategy_id or cls.STRATEGY_ID_RIGHT_SIDE

        # 1. 获取指标数据（需要至少2天用于MACD金叉判断）
        indicators = IndicatorService.get_recent_indicators(db, etf_code, limit=5)
        if len(indicators) < 2:
            logger.warning(f"ETF {etf_code} 指标数据不足，无法生成信号")
            return None

        # 2. 获取最新价格数据
        quote = QuoteService.get_latest_quote(db, etf_code)
        if quote is None:
            logger.warning(f"ETF {etf_code} 无价格数据，无法生成信号")
            return None

        # 3. 检查是否为停牌日
        if quote.trade_status == 0:
            logger.info(f"ETF {etf_code} 停牌中，不生成信号")
            return None

        # 4. 判断信号
        signal = None

        # 优先检查卖出信号（如果有持仓）
        if entry_price is not None:
            signal = generate_sell_signal(
                etf_code=etf_code,
                indicators=indicators,
                quote=quote,
                entry_price=entry_price,
                highest_price=highest_price,
                strategy_id=strategy_id,
            )
            if signal:
                return signal

        # 检查买入信号
        signal = generate_buy_signal(
            etf_code=etf_code,
            indicators=indicators,
            quote=quote,
            strategy_id=strategy_id,
        )
        if signal:
            return signal

        # 无信号时返回持有
        return generate_hold_signal(
            etf_code=etf_code,
            quote=quote,
            strategy_id=strategy_id,
        )

    @classmethod
    def generate_signals_for_all(
        cls,
        db: Optional[Session] = None,
        positions: Optional[Dict[str, Dict[str, Decimal]]] = None,
    ) -> List[SignalModel]:
        """为所有ETF生成交易信号.

        Args:
            db: 数据库会话，不传则自动创建
            positions: 持仓信息，格式 {"etf_code": {"entry_price": x, "highest_price": y}}

        Returns:
            信号列表

        Example:
            >>> positions = {"510300": {"entry_price": Decimal("3.9"), "highest_price": Decimal("4.1")}}
            >>> signals = SignalService.generate_signals_for_all(positions=positions)
        """
        positions = positions or {}

        def _generate(session: Session) -> List[SignalModel]:
            signals = []

            # 获取所有ETF
            etfs = ETFRepository.get_all_etfs(session)
            if not etfs:
                logger.warning("ETF列表为空，无法生成信号")
                return []

            for etf in etfs:
                etf_code = etf.etf_code

                # 获取持仓信息
                position = positions.get(etf_code, {})
                entry_price = position.get("entry_price")
                highest_price = position.get("highest_price")

                try:
                    signal = cls.generate_signal_for_etf(
                        db=session,
                        etf_code=etf_code,
                        entry_price=entry_price,
                        highest_price=highest_price,
                    )
                    if signal:
                        signals.append(signal)
                except Exception as e:
                    logger.error(f"ETF {etf_code} 信号生成失败: {e}")

            return signals

        if db is not None:
            signals = _generate(db)
        else:
            with db_session() as session:
                signals = _generate(session)

        logger.info(f"共生成 {len(signals)} 个信号")
        return signals

    @classmethod
    def save_signal(cls, signal: SignalModel, db: Optional[Session] = None) -> int:
        """保存信号到数据库.

        Args:
            signal: 信号模型
            db: 数据库会话

        Returns:
            信号ID
        """
        def _save(session: Session) -> int:
            schema = signal.to_schema()
            session.add(schema)
            session.flush()
            return schema.id

        if db is not None:
            signal_id = _save(db)
        else:
            with db_session() as session:
                signal_id = _save(session)

        logger.info(f"信号已保存，ID: {signal_id}")
        return signal_id

    @classmethod
    def save_signals(cls, signals: List[SignalModel], db: Optional[Session] = None) -> int:
        """批量保存信号.

        Args:
            signals: 信号列表
            db: 数据库会话

        Returns:
            保存数量
        """
        if not signals:
            return 0

        count = 0
        for signal in signals:
            try:
                cls.save_signal(signal, db)
                count += 1
            except Exception as e:
                logger.error(f"保存信号失败: {e}")

        return count

    @classmethod
    def get_active_signals(cls, db: Optional[Session] = None) -> List[SignalModel]:
        """获取当前有效信号.

        Args:
            db: 数据库会话

        Returns:
            有效信号列表
        """
        def _get(session: Session) -> List[SignalModel]:
            schemas = SignalRepository.get_active_signals(session)
            return [SignalModel.from_schema(s) for s in schemas]

        if db is not None:
            return _get(db)
        else:
            with db_session() as session:
                return _get(session)

    # ==================== 信号分析接口 ====================

    @classmethod
    def analyze_etf(
        cls,
        db: Session,
        etf_code: str,
        entry_price: Optional[Decimal] = None,
        highest_price: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """分析单个ETF的技术状态.

        用于报告输出或调试，返回详细的判断结果。

        Args:
            db: 数据库会话
            etf_code: ETF代码
            entry_price: 持仓成本价
            highest_price: 持仓期间最高价

        Returns:
            分析结果字典

        Example:
            >>> result = SignalService.analyze_etf(db, "510300")
            >>> print(result["buy_check"]["score"])
            4
        """
        # 获取数据
        indicators = IndicatorService.get_recent_indicators(db, etf_code, limit=5)
        quote = QuoteService.get_latest_quote(db, etf_code)

        result = {
            "etf_code": etf_code,
            "trade_date": quote.trade_date if quote else None,
            "close_px": quote.close_px if quote else None,
            "premium_rate": quote.premium_rate if quote else None,
            "buy_check": None,
            "sell_check": None,
            "signal": None,
        }

        if len(indicators) < 2 or quote is None:
            result["error"] = "数据不足"
            return result

        # 买入检查
        buy_check = check_buy_signal(indicators, quote)
        result["buy_check"] = {
            "passed": buy_check.passed,
            "score": buy_check.score,
            "score_details": buy_check.score_details,
            "trend_confirmed": buy_check.trend_confirmed,
            "ma_bullish": buy_check.ma_bullish,
            "macd_golden_cross": buy_check.macd_golden_cross,
            "volume_confirmed": buy_check.volume_confirmed,
            "not_overbought": buy_check.not_overbought,
            "risk_warning": buy_check.risk_check.warning,
        }

        # 卖出检查
        sell_check = check_sell_signal(indicators, quote, entry_price, highest_price)
        result["sell_check"] = {
            "triggered": sell_check.triggered,
            "trigger_reason": sell_check.trigger_reason,
            "trend_reversal": sell_check.trend_reversal,
            "macd_death_cross": sell_check.macd_death_cross,
            "hard_stop_loss": sell_check.hard_stop_loss,
            "trailing_stop": sell_check.trailing_stop,
        }

        # 最新指标
        latest = indicators[-1]
        result["indicators"] = {
            "ma5": float(latest.ma5) if latest.ma5 else None,
            "ma10": float(latest.ma10) if latest.ma10 else None,
            "ma20": float(latest.ma20) if latest.ma20 else None,
            "macd_dif": float(latest.macd_dif) if latest.macd_dif else None,
            "macd_dea": float(latest.macd_dea) if latest.macd_dea else None,
            "adx": float(latest.adx) if latest.adx else None,
            "adx_plus_di": float(latest.adx_plus_di) if latest.adx_plus_di else None,
            "adx_minus_di": float(latest.adx_minus_di) if latest.adx_minus_di else None,
            "rsi_6": float(latest.rsi_6) if latest.rsi_6 else None,
            "volume_ratio": float(latest.volume_ratio) if latest.volume_ratio else None,
        }

        return result


if __name__ == "__main__":
    # 测试：分析所有ETF
    with db_session() as db:
        etfs = ETFRepository.get_all_etfs(db)
        for etf in etfs[:5]:  # 只测试前5个
            result = SignalService.analyze_etf(db, etf.etf_code)
            print(f"\n=== {etf.etf_code} ===")
            print(f"收盘价: {result.get('close_px')}")
            print(f"溢价率: {result.get('premium_rate')}%")
            if result.get("buy_check"):
                print(f"买入评分: {result['buy_check']['score']}/5")
                print(f"评分细节: {result['buy_check']['score_details']}")
            if result.get("sell_check"):
                print(f"卖出触发: {result['sell_check']['triggered']}")