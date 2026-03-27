import baostock as bs
from typing import Optional, List, Dict, Any

from src.utils import get_logger, rate_limit, retry_on_error


logger = get_logger(__name__)
GOOD_STATUS_CODE = "0"


@rate_limit(min_interval=6.0, key="baostock")
@retry_on_error(max_retries=3, retry_delay=8.0)
def get_etf_metric_data_from_baostock(
    symbol: str,
    start_date: str,
    end_date: str,
    fields: str = "date, code, open, high, low, close, volume, amount, turn, tradestatus"
) -> Optional[List[Dict[str, Any]]]:
    """
    从 BaoStock 提供的接口获取指定 ETF 的指标数据.

    Args:
        symbol: ETF 代码 (e.g., "159227")
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        fields: 指标字段 (默认包含 "date, code, open, high, low, close, volume, amount, turn, tradestatus")

    Returns:
        ETF 指标数据 DataFrame
    """
    lg = bs.login()
    if lg.error_code != GOOD_STATUS_CODE:
        logger.error(f"登录 BaoStock 失败， 错误码: {lg.error_code}, 错误信息: {lg.error_msg}")
        return None
    
    # 根据ETF编码开头数字判断市场，目前只支持A股市场
    market_label = "sz" if symbol.startswith("1") else "sh"
    
    bs_raw_data = bs.query_history_k_data_plus(
        code=f"{market_label}.{symbol}",
        fields=fields,
        start_date=start_date, 
        end_date=end_date,
        frequency="d", 
        adjustflag="2"  # 默认前复权
    )

    if bs_raw_data.error_code != GOOD_STATUS_CODE:
        logger.error(f"查询 BaoStock 失败， 错误码: {bs_raw_data.error_code}, 错误信息: {bs_raw_data.error_msg}")
        return None
    
    data_list = []
    while (bs_raw_data.error_code == GOOD_STATUS_CODE) and bs_raw_data.next():
        row_data = bs_raw_data.get_row_data()
        data = {
            "trade_date": row_data[0], 
            "symbol": symbol,
            "open_px": float(row_data[2]),
            "high_px": float(row_data[3]),
            "low_px": float(row_data[4]),
            "close_px": float(row_data[5]),
            "volume": int(float(row_data[6]) / 100),  # baostock提供的单位是股，转换为手
            "amount": float(row_data[7]),
            "turnover_rate": float(row_data[8]) if row_data[8] != "" else 0.0,
            "trade_status": int(row_data[9])
        }
        data_list.append(data)
    
    bs.logout()
    return data_list


if __name__ == '__main__':
    symbol = "159227"
    start_date = "2026-03-01"
    end_date = "2026-03-27"
    fields = "date, code, open, high, low, close, volume, amount, turn, tradestatus"
    data_lst = get_etf_metric_data_from_baostock(symbol, start_date, end_date, fields)
    for data in data_lst:
        # 查看baostock获取数据，是否会获取非交易日数据
        print(data.get("trade_date"))
