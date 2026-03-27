import sys
import json
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

from src.utils import get_logger, get_random_headers, rate_limit


logger = get_logger(__name__)


@rate_limit(min_interval=1.0, key="eastmoney")
def get_etf_info(symbol: str) -> Optional[Dict[str, Any]]:
    """
    从东方财富网获取ETF的基础信息。

    Args:
        symbol: ETF代码

    Returns:
        dict or None
        ETF基础信息，每条记录包含
            ETF代码(etf_code)
            ETF名称(etf_name)
            市场代码(market)
            类别(category)
            跟踪指数(tracking_index)
            基金公司(fund_company)
            资产规模(亿元)(aum)
            费率(expense_ratio)
            成立日期(inception_date)。
    """
    # 验证ETF代码格式
    if not re.match(r'^\d{6}$', symbol):
        logger.error(f"无效的ETF代码格式: {symbol}")
        return None
    
    # 构建请求URL
    url = f'http://fundf10.eastmoney.com/jbgk_{symbol}.html'
    headers = get_random_headers()
    results = {"etf_code": symbol, "market": "CN"}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        # 解析HTML内容
        soup = BeautifulSoup(response.text, 'html.parser')
        # 查找所有表格
        tables = soup.find_all("table")
        if not tables:
            logger.error(f"未找到ETF {symbol} 的基础信息表格")
            return None
        # 遍历表格提取信息
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    # 每两个单元格为一组
                    for i in range(0, len(cells)-1, 2):
                        key = cells[i].get_text(strip=True)
                        value = cells[i+1].get_text(strip=True)
                        
                        # 提取基金简称
                        if "基金简称" in key:
                            results["etf_name"] = value
                        # 提取基金类型，去掉"xxx型-"结构的类型前缀
                        elif "基金类型" in key:
                            results["category"] = re.sub(r'^[\u4e00-\u9fa5]+型-', '', value)
                        # 提取跟踪指数
                        elif "跟踪标的" in key:
                            results["tracking_index"] = value
                        # 提取基金公司
                        elif "基金管理人" in key:
                            results["fund_company"] = value
                        # 提取资产规模
                        elif "资产规模" in key:
                            match = re.search(r'([\d.]+)亿元', value)
                            if match:
                                results["aum"] = match.group(1)
                            else:
                                results["aum"] = None
                        # 提取费率
                        elif key == "管理费率":
                            match = re.search(r'([\d.]+)%', value)
                            if match:
                                results["expense_ratio"] = match.group(1) + '%'
                            else:
                                results["expense_ratio"] = None
                        # 提取成立日期
                        elif key == "成立日期" or "成立日期/规模" in key:
                            match = re.search(r'(\d{4})年(\d{2})月(\d{2})日', value)
                            if match:
                                results["inception_date"] = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                            else:
                                results["inception_date"] = None
        
        return results if results.get("aum") else None

    except requests.exceptions.Timeout:
        logger.error(f"请求ETF {symbol} 基础信息超时")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"请求ETF {symbol} 基础信息失败: {e}")
        return None
    except Exception as e:
        logger.error(f"解析ETF {symbol} 基础信息失败: {e}")
        return None


if __name__ == '__main__':
    symbol = "513400"
    info = get_etf_info(symbol)
    if info:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"获取ETF {symbol} 基础信息失败")
