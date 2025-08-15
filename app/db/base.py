from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import MetaData

class Base(DeclarativeBase):
    metadata = MetaData()

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return cls.__name__.lower()