from sqlalchemy import Column
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class ItemModel(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    name = Column(String, unique=True, nullable=False)
    expires_at = Column(String, nullable=True)
    notified_14_days = Column(Integer, default=0)