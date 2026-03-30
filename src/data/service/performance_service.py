"""信号性能追踪服务.

负责信号性能记录的初始化、每日更新、收益计算、评分等功能。

使用流程：
    1. Morning Job: 创建 performance 记录（status=PENDING_INIT）
    2. Evening Job:
        - 初始化 PENDING_INIT 记录（更新 reference_price, hold_start_date, status=ACTIVE）
        - 更新 ACTIVE 记录的收益、极值、目标达成等
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.data.database import db_session
from src.data.models.performance import PerformanceModel, PerformanceStatus
from src.data.models.signal import SignalModel
from src.data.repository.performance_repo import PerformanceRepository
from src.data.repository.quote_repo import QuoteRepository
from src.data.repository.signal_repo import SignalRepository
from src.utils import get_logger


logger = get_logger(__name__)


@dataclass
class UpdateResult:
    """更新结果."""

    updated_count: int = 0
    completed_count: int = 0
    expired_count: int = 0


class PerformanceService:
    """信号性能追踪服务.

    提供性能记录的创建、初始化、更新、评分等功能。
    """

    @classmethod
    def create_performance_for_signal(
        cls,
        db: Session,
        signal: SignalModel,
    ) -> Optional[PerformanceModel]:
        """为信号创建 performance 记录.

        仅 BUY/SELL 信号创建 performance，HOLD 信号不创建。

        Args:
            db: 数据库会话
            signal: 信号模型

        Returns:
            PerformanceModel 或 None
        """
        # HOLD 信号不创建 performance
        if signal.signal_type == "HOLD":
            return None

        # 检查是否已存在
        existing = PerformanceRepository.get_performance_by_signal(db, signal.id)
        if existing:
            logger.debug(f"Signal {signal.id} performance already exists")
            return PerformanceModel.from_schema(existing)

        # 创建 performance 记录
        performance = PerformanceModel(
            signal_id=signal.id,
            etf_code=signal.etf_code,
            reference_price=signal.trigger_price,  # T-1 收盘价（占位）
            hold_start_date=None,  # 待收盘后确定
            performance_status=PerformanceStatus.PENDING_INIT.value,
        )

        PerformanceRepository.create_performance(db, performance)
        logger.info(f"Created performance for signal {signal.id}, etf={signal.etf_code}")

        return performance

    @classmethod
    def init_pending_performances(cls, db: Session, signal_date: date) -> int:
        """初始化待初始化的 performance 记录.

        将 reference_price 从 T-1 收盘价更新为 T 收盘价。

        Args:
            db: 数据库会话
            signal_date: T 日（今日收盘日期）

        Returns:
            初始化的记录数
        """
        # 获取 PENDING_INIT 记录
        pending_records = PerformanceRepository.get_pending_init_performances(db)

        if not pending_records:
            logger.info("No pending_init performances to initialize")
            return 0

        # 提取 ETF 代码
        etf_codes = list(set(r.etf_code for r in pending_records))

        # 批量获取今日收盘价
        today_quotes = QuoteRepository.get_quotes_by_date(db, signal_date, etf_codes)
        quote_map = {q.etf_code: q.close_px for q in today_quotes if q.close_px is not None}

        # 初始化每条记录
        count = 0
        for record in pending_records:
            close_px = quote_map.get(record.etf_code)

            if close_px is None:
                logger.warning(
                    f"ETF {record.etf_code} 无 {signal_date} 收盘价，跳过初始化"
                )
                continue

            # 更新持仓基准价
            record.reference_price = close_px
            record.hold_start_date = signal_date
            record.performance_status = PerformanceStatus.ACTIVE.value

            PerformanceRepository.update_performance_record(db, record)
            count += 1

            logger.debug(
                f"Initialized performance id={record.id}, etf={record.etf_code}, "
                f"reference_price={close_px}, hold_start={signal_date}"
            )

        logger.info(f"Initialized {count} pending_init performances")
        return count

    @classmethod
    def update_active_performances(
        cls,
        db: Session,
        signal_date: date,
    ) -> UpdateResult:
        """更新活跃追踪的 performance 记录.

        Args:
            db: 数据库会话
            signal_date: T 日（今日收盘日期）

        Returns:
            UpdateResult: 包含 updated_count, completed_count, expired_count
        """
        # 获取 ACTIVE 记录
        active_records = PerformanceRepository.get_active_performances(db)

        if not active_records:
            logger.info("No active performances to update")
            return UpdateResult()

        # 批量获取持仓期间的历史数据
        price_history = cls._batch_get_hold_period_prices(db, active_records, signal_date)

        # 批量获取对应的 signal 信息
        signal_map = cls._batch_get_signals(db, active_records)

        result = UpdateResult()

        for record in active_records:
            etf_code = record.etf_code
            signal = signal_map.get(record.signal_id)

            if signal is None:
                logger.warning(f"Signal {record.signal_id} not found, skip")
                continue

            # 获取持仓期间价格序列
            prices = price_history.get(etf_code, {}).get(record.hold_start_date, [])

            if not prices:
                logger.warning(f"ETF {etf_code} 无持仓期间数据")
                continue

            # 计算持仓天数（交易日数）
            hold_days = len(prices) - 1  # 价格序列包含持仓开始日

            # 根据持仓天数计算指标
            cls._calculate_returns(record, prices, hold_days)
            cls._calculate_extremes(record, prices, hold_days)
            cls._calculate_drawdowns(record, prices, hold_days)
            cls._check_target_stop(record, prices, signal, hold_days)

            # 判断是否完成
            completed = cls._check_completion(record, signal, signal_date, hold_days)

            if completed:
                if record.performance_status == PerformanceStatus.EXPIRED.value:
                    result.expired_count += 1
                else:
                    record.performance_status = PerformanceStatus.COMPLETED.value
                    result.completed_count += 1

                # 计算评分
                record.score = cls._calculate_score(record)

            PerformanceRepository.update_performance_record(db, record)
            result.updated_count += 1

        logger.info(
            f"Updated {result.updated_count} performances, "
            f"completed={result.completed_count}, expired={result.expired_count}"
        )
        return result

    # ==================== 私有方法 ====================

    @classmethod
    def _batch_get_hold_period_prices(
        cls,
        db: Session,
        records: List,
        signal_date: date,
    ) -> Dict[str, Dict[date, List[Decimal]]]:
        """批量获取持仓期间的价格数据.

        Args:
            db: 数据库会话
            records: performance 记录列表
            signal_date: 今日日期

        Returns:
            {
                etf_code: {
                    hold_start_date: [price_day0, price_day1, ..., price_today]
                }
            }
            索引 0 = hold_start_date 收盘价
            索引 N = signal_date 收盘价
        """
        # 确定查询范围
        min_start_date = min(r.hold_start_date for r in records if r.hold_start_date)

        # 提取 ETF 代码
        etf_codes = list(set(r.etf_code for r in records))

        # 批量查询
        quotes = QuoteRepository.get_quotes_between(
            db, etf_codes, min_start_date, signal_date
        )

        # 组织数据结构：{etf_code: {trade_date: close_px}}
        date_price_map: Dict[str, Dict[date, Decimal]] = {}
        for q in quotes:
            if q.etf_code not in date_price_map:
                date_price_map[q.etf_code] = {}
            if q.close_px is not None:
                date_price_map[q.etf_code][q.trade_date] = Decimal(str(q.close_px))

        # 转换为价格序列（按日期升序）
        result: Dict[str, Dict[date, List[Decimal]]] = {}

        for record in records:
            etf_code = record.etf_code
            hold_start = record.hold_start_date

            if etf_code not in date_price_map:
                continue

            # 获取持仓开始日到今日的价格
            etf_prices = date_price_map[etf_code]
            dates = sorted(d for d in etf_prices.keys() if d >= hold_start)
            prices = [etf_prices[d] for d in dates]

            if etf_code not in result:
                result[etf_code] = {}
            result[etf_code][hold_start] = prices

        return result

    @classmethod
    def _batch_get_signals(
        cls,
        db: Session,
        records: List,
    ) -> Dict[int, SignalModel]:
        """批量获取信号信息.

        Args:
            db: 数据库会话
            records: performance 记录列表

        Returns:
            {signal_id: SignalModel}
        """
        signal_ids = list(set(r.signal_id for r in records))
        result = {}

        for signal_id in signal_ids:
            signal_schema = SignalRepository.get_signal_by_id(db, signal_id)
            if signal_schema:
                result[signal_id] = SignalModel.from_schema(signal_schema)

        return result

    @classmethod
    def _calculate_returns(
        cls,
        record,
        prices: List[Decimal],
        hold_days: int,
    ) -> None:
        """计算持仓收益.

        Args:
            record: performance 记录
            prices: 价格序列（索引0=持仓开始日）
            hold_days: 持仓天数
        """
        if not prices or len(prices) < 2:
            return

        reference_price = prices[0]

        # return_Nd = (prices[N] - prices[0]) / prices[0]
        # prices[1] 是持仓第1日收盘，prices[N] 是持仓第N日收盘

        if hold_days >= 1 and len(prices) > 1:
            record.return_1d = (prices[1] - reference_price) / reference_price

        if hold_days >= 3 and len(prices) > 3:
            record.return_3d = (prices[3] - reference_price) / reference_price

        if hold_days >= 5 and len(prices) > 5:
            record.return_5d = (prices[5] - reference_price) / reference_price

        if hold_days >= 10 and len(prices) > 10:
            record.return_10d = (prices[10] - reference_price) / reference_price

        if hold_days >= 20 and len(prices) > 20:
            record.return_20d = (prices[20] - reference_price) / reference_price

    @classmethod
    def _calculate_extremes(
        cls,
        record,
        prices: List[Decimal],
        hold_days: int,
    ) -> None:
        """计算持仓期间价格极值.

        注意：极值范围是 prices[1:N+1]，不包含 prices[0]（持仓开始日）
        因为持仓开始日的价格是"入场价"，不是"持仓后的波动"。

        Args:
            record: performance 记录
            prices: 价格序列
            hold_days: 持仓天数
        """
        if len(prices) < 2:
            return

        # 持仓第1日到第N日的极值
        if hold_days >= 1 and len(prices) > 1:
            record.max_price_1d = max(prices[1:2])
            record.min_price_1d = min(prices[1:2])

        if hold_days >= 3 and len(prices) > 3:
            record.max_price_3d = max(prices[1:4])
            record.min_price_3d = min(prices[1:4])

        if hold_days >= 5 and len(prices) > 6:
            record.max_price_5d = max(prices[1:6])
            record.min_price_5d = min(prices[1:6])

        if hold_days >= 10 and len(prices) > 11:
            record.max_price_10d = max(prices[1:11])
            record.min_price_10d = min(prices[1:11])

        if hold_days >= 20 and len(prices) > 21:
            record.max_price_20d = max(prices[1:21])
            record.min_price_20d = min(prices[1:21])

    @classmethod
    def _calculate_drawdowns(
        cls,
        record,
        prices: List[Decimal],
        hold_days: int,
    ) -> None:
        """计算最大回撤.

        Args:
            record: performance 记录
            prices: 价格序列
            hold_days: 持仓天数
        """
        if len(prices) < 2:
            return

        if hold_days >= 5 and len(prices) > 5:
            record.max_drawdown_5d = cls._calc_max_drawdown(prices[1:6])

        if hold_days >= 20 and len(prices) > 20:
            record.max_drawdown_20d = cls._calc_max_drawdown(prices[1:21])

    @staticmethod
    def _calc_max_drawdown(prices: List[Decimal]) -> Decimal:
        """计算给定价格序列的最大回撤.

        最大回撤 = max( (peak - trough) / peak )

        Args:
            prices: 价格序列

        Returns:
            最大回撤（正数）
        """
        if not prices:
            return Decimal("0")

        peak = prices[0]
        max_dd = Decimal("0")

        for price in prices:
            if price > peak:
                peak = price
            if peak > 0:
                dd = (peak - price) / peak
                if dd > max_dd:
                    max_dd = dd

        return max_dd

    @classmethod
    def _check_target_stop(
        cls,
        record,
        prices: List[Decimal],
        signal: SignalModel,
        hold_days: int,
    ) -> None:
        """检查是否触及目标价或止损价.

        Args:
            record: performance 记录
            prices: 价格序列
            signal: 关联的信号
            hold_days: 持仓天数
        """
        if len(prices) < 2:
            return

        # 用持仓期间最低价判断止损（遍历检查首次触及）
        if signal.stop_loss and not record.hit_stop_loss:
            for i, price in enumerate(prices[1:], start=1):  # 从持仓第1日开始
                if price <= signal.stop_loss:
                    record.hit_stop_loss = True
                    record.hit_stop_loss_days = i  # 持仓第N日触及
                    break

        # 用持仓期间最高价判断目标（遍历检查首次触及）
        if signal.target_price and not record.hit_target:
            for i, price in enumerate(prices[1:], start=1):
                if price >= signal.target_price:
                    record.hit_target = True
                    record.hit_target_days = i
                    break

    @classmethod
    def _check_completion(
        cls,
        record,
        signal: SignalModel,
        signal_date: date,
        hold_days: int,
    ) -> bool:
        """判断 performance 是否应标记为完成.

        Args:
            record: performance 记录
            signal: 关联的信号
            signal_date: 今日日期
            hold_days: 持仓天数

        Returns:
            是否完成
        """
        # 条件1：触及止损或目标
        if record.hit_stop_loss or record.hit_target:
            return True

        # 条件2：超过有效期
        if signal.valid_until and signal_date > signal.valid_until:
            record.performance_status = PerformanceStatus.EXPIRED.value
            return True

        # 条件3：价格跌破失效价
        if signal.invalidation_price:
            # 获取最新价格
            latest_price = getattr(record, "min_price_5d", None) or getattr(record, "min_price_3d", None) or getattr(record, "min_price_1d", None)
            if latest_price is not None and latest_price < signal.invalidation_price:
                return True

        # 条件4：持仓超过20日，自动完成评分
        if hold_days >= 20:
            return True

        return False

    @classmethod
    def _calculate_score(cls, record) -> int:
        """计算信号评分（1-10分）.

        评分规则：
            基础分：5分

            收益分（return_20d）：
              > 15%   +3分
              > 10%   +2分
              > 5%    +1分
              > 0     +0分
              < -5%   -1分
              < -8%   -2分

            回撤分（max_drawdown_20d）：
              < 3%    +1分
              < 5%    +0分
              5-8%    -1分
              8-12%   -2分
              > 12%   -3分

            目标达成（hit_target）：
              3日内达成   +2分
              5日内达成   +1分
              10日内达成  +0分
              未达成      不加分

            止损触发（hit_stop_loss）：
              触发    -3分

        Args:
            record: performance 记录

        Returns:
            评分（1-10）
        """
        score = 5

        # 收益分
        if record.return_20d is not None:
            ret = float(record.return_20d) * 100  # 转为百分比
            if ret > 15:
                score += 3
            elif ret > 10:
                score += 2
            elif ret > 5:
                score += 1
            elif ret < -8:
                score -= 2
            elif ret < -5:
                score -= 1

        # 回撤分
        if record.max_drawdown_20d is not None:
            dd = float(record.max_drawdown_20d) * 100
            if dd < 3:
                score += 1
            elif dd < 5:
                # 不加分不扣分
                pass
            elif dd < 8:
                score -= 1
            elif dd < 12:
                score -= 2
            else:
                score -= 3

        # 目标达成分
        if record.hit_target and record.hit_target_days:
            if record.hit_target_days <= 3:
                score += 2
            elif record.hit_target_days <= 5:
                score += 1
            # 10日内不加分

        # 止损扣分
        if record.hit_stop_loss:
            score -= 3

        # 限制范围 1-10
        score = max(1, min(10, score))

        return score


if __name__ == "__main__":
    # 测试：计算最大回撤
    test_prices = [
        Decimal("3.95"),  # 持仓开始日
        Decimal("4.00"),  # 持仓第1日
        Decimal("4.10"),  # 持仓第2日
        Decimal("4.05"),  # 持仓第3日
        Decimal("3.90"),  # 持仓第4日 - 回撤
        Decimal("4.00"),  # 持仓第5日
    ]

    dd = PerformanceService._calc_max_drawdown(test_prices[1:6])
    print(f"最大回撤: {float(dd)*100:.2f}%")

    # 预期：(4.10 - 3.90) / 4.10 = 4.88%