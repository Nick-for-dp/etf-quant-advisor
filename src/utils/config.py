"""配置加载模块.

负责读取并解析 YAML 配置文件, 支持环境变量替换.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# 在模块加载时加载 .env 文件
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")


class Config:
    """配置管理类.

    从 YAML 文件加载配置, 支持 ${VAR:-default} 格式的环境变量替换.

    Attributes:
        _config: 内部配置字典.
    """

    def __init__(self, config_path: Path | None = None):
        """初始化配置.

        Args:
            config_path: 配置文件路径, 默认为项目根目录的 config/settings.yaml.
        """
        if config_path is None:
            # 从当前文件位置推算项目根目录: src/utils/config.py -> 根目录
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "settings.yaml"

        self._config = self._load_yaml(config_path)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """加载并解析 YAML 文件, 支持环境变量替换.

        Args:
            path: YAML 文件路径.

        Returns:
            解析后的配置字典.
        """
        content = path.read_text(encoding="utf-8")
        # 替换 ${VAR:-default} 格式的环境变量
        content = self._replace_env_vars(content)
        return yaml.safe_load(content)

    def _replace_env_vars(self, content: str) -> str:
        """替换字符串中的环境变量.

        支持的格式:
            - ${VAR}: 从环境变量读取, 不存在则替换为空字符串
            - ${VAR:-default}: 从环境变量读取, 不存在则使用默认值

        Args:
            content: 原始内容.

        Returns:
            替换后的内容.
        """
        # 匹配 ${VAR} 或 ${VAR:-default} 格式
        pattern = r'\$\{([^}]+)\}'

        def replace(match: re.Match) -> str:
            var_expr = match.group(1)
            if ':-' in var_expr:
                # ${VAR:-default} 格式
                var_name, default = var_expr.split(':-', 1)
                return os.getenv(var_name, default)
            else:
                # ${VAR} 格式
                return os.getenv(var_expr, '')

        return re.sub(pattern, replace, content)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项.

        支持点号分隔的嵌套键, 如 "database.host".

        Args:
            key: 配置键名.
            default: 默认值, 键不存在时返回.

        Returns:
            配置值或默认值.
        """
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def database(self) -> dict[str, Any]:
        """获取数据库配置."""
        return self._config.get('database', {})

    @property
    def watchlist(self) -> list[dict[str, str]]:
        """获取监控 ETF 列表.

        Returns:
            ETF 列表, 每个元素包含 code, name, market 字段.
            如果配置中没有 watchlist, 返回空列表.
        """
        return self._config.get('watchlist', [])


# 全局配置实例 (延迟加载)
_config_instance: Config | None = None


def get_config() -> Config:
    """获取全局配置实例.

    单例模式, 首次调用时加载配置.

    Returns:
        Config 实例.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


if __name__ == "__main__":
    config = get_config()
    print(config.database)
