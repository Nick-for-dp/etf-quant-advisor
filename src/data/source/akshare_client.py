import akshare as ak
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any

from src.utils import get_logger, rate_limit, retry_on_error
from src.data.models.quote import QuoteModel
from src.data.source.baostock_client import get_etf_metric_data_from_baostock


logger = get_logger(__name__)


def get_previous_date(date_str: str) -> str:
    """获取前一天的日期字符串，格式为 YYYYMMDD"""
    date_obj = datetime.strptime(date_str, "%Y%m%d")
    previous_date = date_obj - timedelta(days=1)
    return previous_date.strftime("%Y%m%d")


def _build_hist_data_list(
    df,
    symbol: str,
    column_map: Dict[str, str],
    date_field_name: str = "日期"
) -> List[Dict[str, Any]]:
    """
    从 DataFrame 构建历史记录列表.

    Args:
        df: 包含历史数据的 DataFrame，必须包含 "日期" 列
        symbol: ETF 代码
        column_map: 列名映射，将 DataFrame 列映射到输出记录字段

    Returns:
        list[dict]
        历史记录列表，每条记录包含
            trade_date: 交易日期
            symbol: ETF 代码
            其他字段，根据 column_map 映射
    """
    raw_hist_dict = df.set_index(date_field_name).to_dict(orient="index")
    hist_list = []
    for trade_date, row in raw_hist_dict.items():
        item = {"trade_date": trade_date, "symbol": symbol}
        for out_key, col_name in column_map.items():
            item[out_key] = row.get(col_name)
        hist_list.append(item)
    return hist_list


@rate_limit(min_interval=6.0, key="akshare")
@retry_on_error(max_retries=3, retry_delay=8.0)
def get_etf_basic_data_from_eastmoney(
    symbol: str,
    start_date: str,
    end_date: str,
    period: str = "daily"
) -> Optional[List[Dict[str, Any]]]:
    """
    直接从东方财富根据开始与结束时间获取ETF基础数据.

    Args:
        symbol: ETF代码
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"
        period: 数据周期，默认 "daily"

    Returns:
        list[dict] or None
        历史行情列表，每条记录包含
            ETF代码(etf_code)
            交易日期(trade_date)
            前复权的最低价(low_px)
            前复权的最高价(high_px)
            前复权的开盘价(open_px)
            前复权的收盘价(close_px)
            成交量(volume)
            成交额(amount)
            换手率(turnover)。
    """
    if not end_date:
        end_date = datetime.today().strftime("%Y%m%d")
    
    try:
        # 由于akshare接口的时间范围前开后闭，因此start_date需要前推一天
        raw_df = ak.fund_etf_hist_em(symbol=symbol, start_date=start_date, end_date=end_date, period=period, adjust="qfq")
        
        if raw_df.empty or raw_df is None:
            logger.warning(f"获取{symbol} {start_date} 至 {end_date} 的数据为空。")
            return None
        
        required_columns = {"日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "换手率"}
        missing_columns = required_columns - set[Any](raw_df.columns)

        if missing_columns:
            logger.warning(f"获取{symbol} {start_date} 至 {end_date} 的数据字段缺失: missing={missing_columns}。")
            return None
        
        column_map = {
            "open_px": "开盘",
            "high_px": "最高",
            "low_px": "最低",
            "close_px": "收盘",
            "volume": "成交量",
            "amount": "成交额",
            "turnover_rate": "换手率",
        }
        hist_data_list = _build_hist_data_list(raw_df, symbol, column_map)
        logger.info(f"成功获取{symbol} {start_date} 至 {end_date} 的数据，数据周期为{period}，记录数为{len(hist_data_list)}。")
        return hist_data_list
    # 网络异常向上传播，由 @retry_on_error 装饰器处理重试
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"数据解析错误 symbol={symbol}，开始时间为{start_date}，结束时间为{end_date}，数据周期为{period}，错误信息：{e}。")
        return None


@rate_limit(min_interval=6.0, key="akshare")
@retry_on_error(max_retries=3, retry_delay=8.0)
def get_etf_metric_data_from_eastmoney(
    symbol: str,
    start_date: str,
    end_date: str,
) -> Optional[List[Dict[str, float]]]:
    """
    从东方财富网获取ETF的单位净值指标，然后基于单位净值计算溢价率。

    Args:
        symbol: ETF代码
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"

    Returns:
        list[dict] or None
        历史行情列表，每条记录包含
            ETF代码(etf_code)
            交易日期(trade_date)
            单位净值(nav)。

    """
    if not end_date:
        end_date = datetime.today().strftime("%Y%m%d")
    
    try:
        # 由于akshare接口的时间范围前开后闭，因此start_date需要前推一天
        raw_df = ak.fund_etf_fund_info_em(fund=symbol, start_date=start_date, end_date=end_date)
        
        if raw_df.empty or raw_df is None:
            logger.warning(f"获取{symbol} {start_date} 至 {end_date} 的单位净值数据为空。")
            return None
        
        required_columns = {"净值日期", "单位净值"}
        missing_columns = required_columns - set[Any](raw_df.columns)

        if missing_columns:
            logger.warning(f"获取{symbol} {start_date} 至 {end_date} 的数据字段缺失: missing={missing_columns}。")
            return None
        
        column_map = {
            "nav": "单位净值"
        }
        hist_metric_data_list = _build_hist_data_list(raw_df, symbol, column_map, date_field_name="净值日期")
        logger.info(f"成功获取{symbol} {start_date} 至 {end_date} 的数据，记录数为{len(hist_metric_data_list)}。")
        return hist_metric_data_list
    # 网络异常向上传播，由 @retry_on_error 装饰器处理重试
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"数据解析错误 symbol={symbol}，开始时间为{start_date}，结束时间为{end_date}，错误信息：{e}。")
        return None
    

def build_quote_data(
    symbol: str,
    start_date: str,
    end_date: str,
) -> Optional[List[QuoteModel]]:
    """
    聚合ETF基础行情数据与净值数据，计算溢价率，生成QuoteModel列表.

    Args:
        symbol: ETF代码
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"

    Returns:
        list[QuoteModel] or None
        聚合后的报价数据列表，若任一数据源返回空则返回None
    """
    # 获取基础行情数据
    basic_data = get_etf_basic_data_from_eastmoney(symbol, start_date, end_date)
    if not basic_data:
        logger.error(f"获取基础行情数据失败，symbol={symbol}，start_date={start_date}，end_date={end_date}")
        return None

    # 获取净值数据
    metric_data = get_etf_metric_data_from_eastmoney(symbol, start_date, end_date)
    if not metric_data:
        logger.error(f"获取净值数据失败，symbol={symbol}，start_date={start_date}，end_date={end_date}")
        return None

    # 构建净值数据字典，以 trade_date 为键
    # 需统一日期格式为 YYYY-MM-DD
    nav_dict: Dict[str, float] = {}
    for item in metric_data:
        trade_date = item.get("trade_date")
        if trade_date:
            # 统一日期格式
            normalized_date = _normalize_date(str(trade_date))
            nav_dict[normalized_date] = item.get("nav")

    # 聚合数据并计算溢价率
    quote_list: List[QuoteModel] = []
    for item in basic_data:
        trade_date_raw = item.get("trade_date")
        if not trade_date_raw:
            continue

        # 统一日期格式
        normalized_date = _normalize_date(str(trade_date_raw))

        # 获取净值，若不存在则为 None
        nav = nav_dict.get(normalized_date)
        close_px = item.get("close_px")

        # 计算溢价率，四舍五入保留两位小数
        premium_rate = None
        if nav is not None and close_px is not None and nav != 0:
            premium_rate = (
                (Decimal(str(close_px)) - Decimal(str(nav))) / Decimal(str(nav)) * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 构建 QuoteModel
        quote = QuoteModel(
            etf_code=symbol,
            trade_date=normalized_date,
            open_px=_to_decimal(item.get("open_px")),
            high_px=_to_decimal(item.get("high_px")),
            low_px=_to_decimal(item.get("low_px")),
            close_px=_to_decimal(close_px),
            volume=item.get("volume"),
            amount=_to_decimal(item.get("amount")),
            turnover=_to_decimal(item.get("turnover_rate")),
            nav=_to_decimal(nav),
            premium_rate=premium_rate,
        )
        quote_list.append(quote)

    logger.info(f"成功聚合{symbol} {start_date} 至 {end_date} 的报价数据，记录数为{len(quote_list)}。")
    return quote_list


def build_quote_data_hybrid(
    symbol: str,
    start_date: str,
    end_date: str,
) -> Optional[List[QuoteModel]]:
    """
    混合数据源获取ETF报价数据.

    行情数据使用 BaoStock，净值数据使用 AkShare（东方财富）。
    相比纯 AkShare 方案，可降低单一数据源被封风险。
    自动填充停牌日/节假日数据，确保日期连续。

    Args:
        symbol: ETF代码
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"

    Returns:
        list[QuoteModel] or None
        聚合后的报价数据列表，若任一数据源返回空则返回None
    """
    # 转换日期格式：YYYYMMDD -> YYYY-MM-DD（BaoStock 需要此格式）
    start_date_fmt = _normalize_date(start_date)
    end_date_fmt = _normalize_date(end_date)

    # 从 BaoStock 获取行情数据
    basic_data = get_etf_metric_data_from_baostock(symbol, start_date_fmt, end_date_fmt)
    if not basic_data:
        logger.error(f"[Hybrid] 获取行情数据失败，symbol={symbol}，start_date={start_date}，end_date={end_date}")
        return None

    # 填充停牌日/节假日数据
    filled_data = _fill_suspended_days(basic_data)

    # 从 AkShare 获取净值数据
    metric_data = get_etf_metric_data_from_eastmoney(symbol, start_date, end_date)
    if not metric_data:
        logger.error(f"[Hybrid] 获取净值数据失败，symbol={symbol}，start_date={start_date}，end_date={end_date}")
        return None

    # 构建净值数据字典，以 trade_date 为键（格式统一为 YYYY-MM-DD）
    nav_dict: Dict[str, float] = {}
    for item in metric_data:
        trade_date = item.get("trade_date")
        if trade_date:
            normalized_date = _normalize_date(str(trade_date))
            nav_dict[normalized_date] = item.get("nav")

    # 聚合数据并计算溢价率
    quote_list: List[QuoteModel] = []
    prev_nav: Optional[float] = None
    prev_premium_rate: Optional[Decimal] = None

    for item in filled_data:
        trade_date_raw = item.get("trade_date")
        if not trade_date_raw:
            continue

        # BaoStock 返回的日期格式为 YYYY-MM-DD
        normalized_date = _normalize_date(str(trade_date_raw))

        # 获取净值，若不存在则使用前一日净值（停牌日场景）
        nav = nav_dict.get(normalized_date)
        if nav is None:
            nav = prev_nav
        else:
            prev_nav = nav

        close_px = item.get("close_px")
        trade_status = item.get("trade_status", 1)

        # 计算溢价率，四舍五入保留两位小数
        premium_rate = None
        if nav is not None and close_px is not None and nav != 0:
            premium_rate = (
                (Decimal(str(close_px)) - Decimal(str(nav))) / Decimal(str(nav)) * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif trade_status == 0:
            # 停牌日使用前一日溢价率
            premium_rate = prev_premium_rate

        # 更新前一日的溢价率
        if premium_rate is not None:
            prev_premium_rate = premium_rate

        # 构建 QuoteModel
        quote = QuoteModel(
            etf_code=symbol,
            trade_date=normalized_date,
            open_px=_to_decimal(item.get("open_px")),
            high_px=_to_decimal(item.get("high_px")),
            low_px=_to_decimal(item.get("low_px")),
            close_px=_to_decimal(close_px),
            volume=item.get("volume"),
            amount=_to_decimal(item.get("amount")),
            turnover=_to_decimal(item.get("turnover_rate")),
            nav=_to_decimal(nav),
            premium_rate=premium_rate,
            trade_status=trade_status,
        )
        quote_list.append(quote)

    logger.info(f"[Hybrid] 成功聚合{symbol} {start_date} 至 {end_date} 的报价数据，记录数为{len(quote_list)}。")
    return quote_list


def _normalize_date(date_str: str) -> str:
    """
    统一日期格式为 YYYY-MM-DD.

    支持输入格式：
        - "2024-01-15" (ISO 格式)
        - "20240115" (紧凑格式)
        - "2024/01/15" (斜杠格式)

    Args:
        date_str: 日期字符串

    Returns:
        格式化后的日期字符串 (YYYY-MM-DD)
    """
    formats = [
        "%Y-%m-%d",
        "%Y%m%d",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def _get_missing_dates(start_date: datetime, end_date: datetime) -> List[datetime]:
    """获取两个日期之间缺失的所有日期（含周末）."""
    missing = []
    current = start_date + timedelta(days=1)
    while current < end_date:
        missing.append(current)
        current += timedelta(days=1)
    return missing


def _fill_suspended_days(
    basic_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    填充停牌日/节假日数据.

    遍历行情数据，检查相邻日期之间是否存在缺失的工作日，
    若存在则填充为停牌日数据。

    Args:
        basic_data: BaoStock 返回的原始行情数据（已按日期排序）
        start_date: 请求的开始日期，格式 YYYY-MM-DD
        end_date: 请求的结束日期，格式 YYYY-MM-DD

    Returns:
        填充后的行情数据列表
    """
    if not basic_data or len(basic_data) < 1:
        return basic_data

    # 按日期排序
    sorted_data = sorted(basic_data, key=lambda x: x.get("trade_date", ""))

    filled_data: List[Dict[str, Any]] = []
    prev_item = None

    for item in sorted_data:
        trade_date_str = item.get("trade_date")
        if not trade_date_str:
            continue

        current_date = datetime.strptime(_normalize_date(str(trade_date_str)), "%Y-%m-%d")

        # 如果存在前一条记录，检查日期间隔
        if prev_item is not None:
            prev_date_str = prev_item.get("trade_date")
            prev_date = datetime.strptime(_normalize_date(str(prev_date_str)), "%Y-%m-%d")

            # 获取缺失的工作日
            missing_dates = _get_missing_dates(prev_date, current_date)

            # 填充缺失日期（停牌日）
            for missing_date in missing_dates:
                suspended_item = {
                    "trade_date": missing_date.strftime("%Y-%m-%d"),
                    "symbol": item.get("symbol"),
                    "open_px": prev_item.get("close_px"),
                    "high_px": prev_item.get("close_px"),
                    "low_px": prev_item.get("close_px"),
                    "close_px": prev_item.get("close_px"),
                    "volume": 0,
                    "amount": 0.0,
                    "turnover_rate": None,
                    "trade_status": 0,  # 停牌
                }
                filled_data.append(suspended_item)

        # 添加当前记录
        filled_data.append(item)
        prev_item = item

    logger.info(f"[填充停牌日] 原始数据 {len(basic_data)} 条，填充后 {len(filled_data)} 条，新增 {len(filled_data) - len(basic_data)} 条停牌日记录")
    return filled_data


def _to_decimal(value: Any) -> Optional[Decimal]:
    """
    将值转换为 Decimal 类型.

    Args:
        value: 待转换的值

    Returns:
        Decimal 类型值，若输入为 None 则返回 None
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


if __name__ == "__main__":
    symbol = "159227"
    start_date = "20260301"
    end_date = "20260315"

    data_lst = get_etf_metric_data_from_eastmoney(symbol, start_date, end_date)
    for data in data_lst:
        # 查看akshare获取数据，是否会获取非交易日数据
        print(data.get("trade_date"))

    # # 测试混合数据源方法（推荐）
    # quote_list = build_quote_data_hybrid(symbol=symbol, start_date=start_date, end_date=end_date)
    # if quote_list:
    #     for quote in quote_list:
    #         status_str = "停牌" if quote.trade_status == 0 else "正常"
    #         print(f"日期: {quote.trade_date}, 状态: {status_str}, 收盘价: {quote.close_px}, 成交量: {quote.volume}, 净值: {quote.nav}, 溢价率: {quote.premium_rate}")
    # else:
    #     print("获取数据失败")
