from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class BondBase(BaseModel):
    isin: str
    name: str
    face_value: float
    lendable_ratio: float
    actual_borrow_ratio: float
    latest_price: Optional[float] = None
    price_source_url: Optional[str] = None
    price_source: Optional[str] = None
    currency: str = 'USD'

class BondCreate(BondBase):
    pass

class QuickAddBondRequest(BaseModel):
    isin: str
    face_value: Optional[float] = 200000.0
    lendable_ratio: Optional[float] = 0.80
    actual_borrow_ratio: Optional[float] = 0.50

class BondUpdate(BaseModel):
    isin: Optional[str] = None
    name: Optional[str] = None
    face_value: Optional[float] = None
    lendable_ratio: Optional[float] = None
    actual_borrow_ratio: Optional[float] = None
    latest_price: Optional[float] = None
    price_source_url: Optional[str] = None
    price_source: Optional[str] = None

class Bond(BondBase):
    id: int
    bank_id: int
    price_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BankBase(BaseModel):
    name: str
    min_maintenance_ratio: float = 130.0
    warning_ratio: float = 140.0
    margin_call_ratio: float = 135.0
    total_loan_amount: float

class BankCreate(BankBase):
    pass

class BankUpdate(BaseModel):
    name: Optional[str] = None
    min_maintenance_ratio: Optional[float] = None
    warning_ratio: Optional[float] = None
    margin_call_ratio: Optional[float] = None
    total_loan_amount: Optional[float] = None

class BankSimple(BankBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Bank(BankSimple):
    bonds: List[Bond] = []

class DashboardBondInfo(Bond):
    market_value_usd: float
    market_value_twd: float
    borrow_amount_usd: float = 0.0
    borrow_amount_twd: float = 0.0

class DashboardData(BaseModel):
    bank_info: BankSimple
    bonds: List[DashboardBondInfo]
    total_market_value_usd: float
    total_market_value_twd: float
    total_floating_loan_usd: float = 0.0
    total_floating_loan_twd: float = 0.0
    total_loan_amount_twd: float
    current_maintenance_ratio: float
    warning_status: str
    exchange_rate: float
