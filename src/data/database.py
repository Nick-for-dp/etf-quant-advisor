"""数据库连接模块.

基于 SQLAlchemy 2.0 实现 PostgreSQL 数据库连接和会话管理.
提供引擎创建、会话工厂、上下文管理器等功能.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.utils import get_config


# -----------------------------------------------------------------------------
# 数据库引擎
# -----------------------------------------------------------------------------

def _build_db_url() -> str:
    """从配置构建数据库连接 URL.

    Returns:
        PostgreSQL 连接 URL, 格式: postgresql+psycopg://user:pass@host:port/db
    """
    cfg = get_config().database
    return (
        f"postgresql+psycopg://"
        f"{cfg['username']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}"
        f"/{cfg['database']}"
    )


def create_db_engine():
    """创建 SQLAlchemy 数据库引擎.

    使用连接池配置优化性能, 支持自动重连.

    Returns:
        SQLAlchemy Engine 实例.
    """
    cfg = get_config().database
    return create_engine(
        _build_db_url(),
        # 连接池配置
        pool_size=cfg.get('pool_size', 5),
        max_overflow=cfg.get('max_overflow', 10),
        pool_timeout=cfg.get('pool_timeout', 30),
        pool_recycle=cfg.get('pool_recycle', 3600),
        # 日志配置
        echo=False,  # 设为 True 可打印 SQL 语句 (调试用途)
    )


# 全局引擎实例 (延迟初始化)
_engine = None


def get_engine():
    """获取全局数据库引擎实例.

    Returns:
        SQLAlchemy Engine 实例.
    """
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


# -----------------------------------------------------------------------------
# 会话管理
# -----------------------------------------------------------------------------

# 会话工厂: 用于创建新的 Session 实例
# 注意: bind 参数在创建会话时动态传递，避免循环依赖和延迟初始化问题
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """生成器方式获取数据库会话.

    适用于 FastAPI 等框架的依赖注入, 自动管理会话生命周期.

    Yields:
        SQLAlchemy Session 实例.

    Example:
        >>> def my_function(db: Session = Depends(get_db)):
        ...     db.query(...)
    """
    db = SessionLocal(bind=get_engine())
    try:
        yield db
        db.commit()  # 自动提交
    except Exception:
        db.rollback()  # 异常时回滚
        raise
    finally:
        db.close()  # 确保关闭


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """上下文管理器方式获取数据库会话.

    使用 with 语句确保会话正确关闭, 推荐用于普通脚本.

    Yields:
        SQLAlchemy Session 实例.

    Example:
        >>> with db_session() as db:
        ...     db.query(...)
        ...     # 自动提交/回滚并关闭
    """
    db = SessionLocal(bind=get_engine())
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

def init_db() -> None:
    """初始化数据库 (创建所有表).

n    根据 SQLAlchemy 模型自动创建数据库表结构.
    注意: 生产环境建议使用 Alembic 迁移工具而非此函数.

    Example:
        >>> from src.data.schema import Base
        >>> init_db()  # 创建所有 Base.metadata 中定义的表
    """
    # 延迟导入, 避免循环依赖
    from src.data.schema import Base

    Base.metadata.create_all(bind=get_engine())


def check_connection() -> bool:
    """检查数据库连接是否正常.

    Returns:
        True: 连接正常
        False: 连接失败

    Example:
        >>> if check_connection():
        ...     print("数据库连接正常")
    """
    try:
        with db_session() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
