"""SQLAlchemy ORM 基础模块.

提供 DeclarativeBase 基类，供所有 Schema 继承。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类.

    所有 ORM Schema 都应继承此类。
    """

    pass