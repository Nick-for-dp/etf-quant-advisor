"""ETF 基础信息服务.

负责整合配置读取、数据获取、模型转换的业务流程编排。
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from src.data.database import db_session
from src.data.models.etf import ETFModel
from src.data.repository.etf_repo import ETFRepository
from src.data.source.request_client import get_etf_info
from src.utils import get_logger
from src.utils.config import get_config


logger = get_logger(__name__)


class ETFService:
    """ETF 基础信息服务类.

    提供关注列表 ETF 信息的同步功能。
    """

    @classmethod
    def get_watchlist_codes(cls) -> List[str]:
        """从配置文件获取关注列表的 ETF 代码.

        Returns:
            ETF 代码列表

        Example:
            >>> codes = ETFService.get_watchlist_codes()
            >>> print(codes)
            ['510300', '512000', '513100']
        """
        config = get_config()
        watchlist = config.watchlist
        codes = [item["code"] for item in watchlist if "code" in item]
        logger.info(f"从配置文件获取到 {len(codes)} 个 ETF 代码")
        return codes

    @classmethod
    def _convert_to_model(cls, raw_data: dict) -> Optional[ETFModel]:
        """将原始数据转换为 ETFModel.

        Args:
            raw_data: get_etf_info 返回的原始数据

        Returns:
            ETFModel 实例，转换失败返回 None
        """
        try:
            # 转换 aum: "23.57" -> Decimal("23.57")
            aum = None
            if raw_data.get("aum"):
                aum = Decimal(raw_data["aum"])

            # 转换 expense_ratio: "0.50%" -> Decimal("0.0050")
            expense_ratio = None
            if raw_data.get("expense_ratio"):
                ratio_str = raw_data["expense_ratio"].replace("%", "")
                expense_ratio = Decimal(ratio_str) / Decimal("100")

            # 转换 inception_date: "2024-01-17" -> date(2024, 1, 17)
            inception_date = None
            if raw_data.get("inception_date"):
                inception_date = date.fromisoformat(raw_data["inception_date"])

            return ETFModel(
                etf_code=raw_data["etf_code"],
                etf_name=raw_data["etf_name"],
                market=raw_data.get("market", "CN"),
                category=raw_data.get("category"),
                tracking_index=raw_data.get("tracking_index"),
                fund_company=raw_data.get("fund_company"),
                aum=aum,
                expense_ratio=expense_ratio,
                inception_date=inception_date,
            )
        except Exception as e:
            logger.error(f"转换 ETF 数据失败: {raw_data.get('etf_code')}, 错误: {e}")
            return None

    @classmethod
    def fetch_etf_info(cls, codes: List[str]) -> List[ETFModel]:
        """批量获取 ETF 基础信息并转换为业务模型.

        Args:
            codes: ETF 代码列表

        Returns:
            ETFModel 列表（仅包含成功获取的数据）

        Example:
            >>> models = ETFService.fetch_etf_info(['510300', '510500'])
            >>> for model in models:
            ...     print(model.etf_code, model.etf_name)
        """
        models: List[ETFModel] = []

        for code in codes:
            raw_data = get_etf_info(code)
            if raw_data is None:
                logger.warning(f"获取 ETF {code} 信息失败，跳过")
                continue

            model = cls._convert_to_model(raw_data)
            if model:
                models.append(model)
                logger.debug(f"成功转换 ETF {code} 数据")
            else:
                logger.warning(f"转换 ETF {code} 数据失败，跳过")

        logger.info(f"成功获取 {len(models)}/{len(codes)} 个 ETF 信息")
        return models

    @classmethod
    def save_to_db(cls, models: List[ETFModel], db: Optional[Session] = None) -> int:
        """将 ETF 信息批量写入数据库.

        Args:
            models: ETFModel 列表
            db: 数据库会话，不传则自动创建

        Returns:
            成功写入的记录数

        Example:
            >>> models = ETFService.fetch_etf_info(['510300', '510500'])
            >>> count = ETFService.save_to_db(models)
            >>> print(f"写入 {count} 条记录")
        """
        # 转换为 ORM Schema 列表
        schemas = [model.to_schema() for model in models]

        def _save(session: Session) -> int:
            ETFRepository.upsert_etf(session, schemas)
            return len(schemas)

        # 判断是否需要自动管理会话
        if db is not None:
            count = _save(db)
        else:
            with db_session() as session:
                count = _save(session)

        logger.info(f"成功写入 {count} 条 ETF 记录到数据库")
        return count

    @classmethod
    def sync_watchlist(cls, save_db: bool = True) -> List[ETFModel]:
        """同步关注列表 ETF 信息（主入口）.

        整合配置读取、数据获取、模型转换、数据库写入的完整流程。

        Args:
            save_db: 是否写入数据库，默认 True

        Returns:
            ETFModel 列表

        Example:
            >>> models = ETFService.sync_watchlist()
            >>> for model in models:
            ...     print(model.etf_code, model.etf_name, model.category)
        """
        logger.info("开始同步关注列表 ETF 信息")

        # 1. 获取关注列表代码
        codes = cls.get_watchlist_codes()
        if not codes:
            logger.warning("关注列表为空，无 ETF 需要同步")
            return []

        # 2. 批量获取 ETF 信息
        models = cls.fetch_etf_info(codes)

        # 3. 写入数据库
        if save_db and models:
            cls.save_to_db(models)

        logger.info(f"同步完成，共获取 {len(models)} 个 ETF 信息")
        return models


if __name__ == "__main__":
    models = ETFService.sync_watchlist()
    for model in models:
        print(model.etf_code, model.etf_name, model.category)
