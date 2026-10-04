from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
import datetime

class Bank(Base):
    __tablename__ = "banks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, index=True)
    min_maintenance_ratio = Column(Float, default=130.0) # 最低維持率
    warning_ratio = Column(Float, default=140.0) # 接近補倉線
    margin_call_ratio = Column(Float, default=135.0) # 需補倉催繳線
    total_loan_amount = Column(Float) # 總借款金額, 台幣固定值, stored in 萬
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    bonds = relationship("Bond", back_populates="bank", cascade="all, delete-orphan", lazy="selectin")


class Bond(Base):
    __tablename__ = "bonds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bank_id = Column(Integer, ForeignKey("banks.id"))
    isin = Column(String, index=True)
    name = Column(String)
    face_value = Column(Float)
    lendable_ratio = Column(Float)
    actual_borrow_ratio = Column(Float)
    
    latest_price = Column(Float, nullable=True)
    price_source_url = Column(String, nullable=True)
    price_source = Column(String, nullable=True)
    price_updated_at = Column(DateTime, nullable=True)
    currency = Column(String, default='USD')

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    bank = relationship("Bank", back_populates="bonds", lazy="selectin")
