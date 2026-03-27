"""ETF 基础信息数据仓库.

提供 ETF 基础信息的 CRUD 操作。
"""

from src.data.schema.etf import ETF


from typing import List, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import ETF


class ETFRepository:
    """ETF 基础信息仓库类.

    方法均为类方法，直接调用，无需实例化。
    """

    @classmethod
    def upsert_etf(
        cls,
        db: Session,
        data: Union[dict, ETF, List[Union[dict, ETF]]],
    ) -> Union[ETF, List[ETF]]:
        """新增或更新 ETF 基础信息.

        根据 etf_code 判断：存在则更新，不存在则插入。
        支持单个或批量操作，输入列表则返回列表。

        Args:
            db: 数据库会话
            data: ETF 数据，支持单个或列表形式的字典/ETF模型实例

        Returns:
            创建或更新后的 ETF 实例（单个输入）
            或 ETF 实例列表（批量输入）

        Example:
            单个录入:
            >>> with db_session() as db:
            ...     etf = ETFRepository.upsert_etf(db, {
            ...         "etf_code": "510300",
            ...         "etf_name": "沪深300ETF",
            ...         "category": "宽基",
            ...     })

            批量录入:
            >>> with db_session() as db:
            ...     etfs = ETFRepository.upsert_etf(db, [
            ...         {"etf_code": "510300", "etf_name": "沪深300ETF"},
            ...         {"etf_code": "510500", "etf_name": "中证500ETF"},
            ...     ])
        """
        # 判断是否为批量操作
        is_batch = isinstance(data, list)
        items: List[Union[dict, ETF]] = data if is_batch else [data]  # type: ignore
        results: List[ETF] = []

        for item in items:
            # 提取数据
            if isinstance(item, ETF):
                etf_code = item.etf_code
                values = {
                    "etf_code": item.etf_code,
                    "etf_name": item.etf_name,
                    "market": item.market,
                    "category": item.category,
                    "tracking_index": item.tracking_index,
                    "fund_company": item.fund_company,
                    "aum": item.aum,
                    "expense_ratio": item.expense_ratio,
                    "inception_date": item.inception_date,
                }
            else:
                etf_code = item["etf_code"]
                values = item.copy()

            # 查询是否存在
            existing = db.get(ETF, etf_code)
            if existing:
                # 更新已有记录
                for key, value in values.items():
                    if key != "etf_code" and hasattr(existing, key):
                        setattr(existing, key, value)
                results.append(existing)
            else:
                # 创建新记录
                new_etf = ETF(**values)
                db.add(new_etf)
                results.append(new_etf)

        db.flush()
        # 单个输入返回单个，批量输入返回列表
        return results if is_batch else results[0]

    @classmethod
    def get_all_etfs(cls, db: Session) -> List[ETF]:
        """获取所有 ETF 列表.

        用于遍历生成信号场景。

        Args:
            db: 数据库会话

        Returns:
            ETF 列表

        Example:
            >>> with db_session() as db:
            ...     etfs = ETFRepository.get_all_etfs(db)
            ...     for etf in etfs:
            ...         print(etf.etf_code, etf.etf_name)
        """
        stmt = select(ETF).order_by(ETF.etf_code)
        return list[ETF](db.execute(stmt).scalars().all())
