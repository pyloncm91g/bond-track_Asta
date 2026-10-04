import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import datetime
import asyncio

from . import models, schemas
from .database import engine, Base, get_db, AsyncSessionLocal
from .services.exchange_rate import ExchangeRateService
from .services.bond_price import fetch_bond_price, lookup_bond_by_isin


logger = logging.getLogger(__name__)

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and seed sample data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(models.Bank))
        if not result.scalars().first():
            # Seed: 玉山銀行 with 5 sample bonds from ISIN Code.txt
            bank = models.Bank(
                name="玉山銀行",
                min_maintenance_ratio=130.0,
                warning_ratio=140.0,
                margin_call_ratio=135.0,
                total_loan_amount=3620.0,  # 3,620 萬 TWD
            )
            db.add(bank)
            await db.commit()
            await db.refresh(bank)

            sample_bonds = [
                {
                    "isin": "US30303M8Q83",
                    "name": "Meta Platforms Inc.",
                    "face_value": 200000,
                    "lendable_ratio": 0.7,
                    "actual_borrow_ratio": 0.6,
                    "latest_price": 98.5,
                    "price_source_url": "https://live.deutsche-boerse.com/bond/us30303m8q83",
                    "price_source": "Deutsche Börse",
                },
                {
                    "isin": "US842434DA71",
                    "name": "Southern California Gas Co. 5.6% 01-APR-2054",
                    "face_value": 200000,
                    "lendable_ratio": 0.85,
                    "actual_borrow_ratio": 0.6,
                    "latest_price": 87.98,
                    "price_source_url": "https://tw.tradingview.com/symbols/FINRA-SRE5771941/",
                    "price_source": "TradingView",
                },
                {
                    "isin": "US931142CK74",
                    "name": "Walmart Inc.",
                    "face_value": 200000,
                    "lendable_ratio": 0.7,
                    "actual_borrow_ratio": 0.6,
                    "latest_price": 102.3,
                    "price_source_url": "https://live.deutsche-boerse.com/bond/us931142ck74",
                    "price_source": "Deutsche Börse",
                },
                {
                    "isin": "US717081CY74",
                    "name": "Pfizer Inc. 7.2% 09/39",
                    "face_value": 200000,
                    "lendable_ratio": 0.7,
                    "actual_borrow_ratio": 0.6,
                    "latest_price": 105.2,
                    "price_source_url": "https://live.deutsche-boerse.com/bond/us717081cy74-pfizer-inc-7-2-09-39?mic=XFRA",
                    "price_source": "Deutsche Börse",
                },
                {
                    "isin": "US20826FAR73",
                    "name": "ConocoPhillips DL-Notes 2016(16/46)",
                    "face_value": 250000,
                    "lendable_ratio": 0.7,
                    "actual_borrow_ratio": 0.6,
                    "latest_price": 108.4,
                    "price_source_url": "https://markets.businessinsider.com/bonds/conocophillips_companydl-notes_201616-46-bond-2046-us20826far73",
                    "price_source": "Business Insider",
                },
            ]

            for b in sample_bonds:
                bond = models.Bond(
                    bank_id=bank.id,
                    **b,
                    price_updated_at=datetime.datetime.utcnow(),
                )
                db.add(bond)
            await db.commit()
            logger.info("Seeded sample data: 玉山銀行 with 5 bonds")

    yield  # App is running

    # Shutdown logic (if needed)


app = FastAPI(title="債券質借風控儀表板", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check ---
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "bonds-dashboard"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    logger.error(f"Global exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


# --- Banks CRUD ---
@app.get("/api/banks", response_model=list[schemas.Bank])
async def list_banks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Bank).options(selectinload(models.Bank.bonds))
    )
    return result.scalars().all()


@app.get("/api/banks/{bank_id}", response_model=schemas.Bank)
async def get_bank(bank_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Bank).where(models.Bank.id == bank_id).options(selectinload(models.Bank.bonds))
    )
    bank = result.scalars().first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    return bank


@app.post("/api/banks", response_model=schemas.Bank)
async def create_bank(
    bank: schemas.BankCreate, db: AsyncSession = Depends(get_db)
):
    db_bank = models.Bank(**bank.model_dump())
    db.add(db_bank)
    await db.commit()
    await db.refresh(db_bank)
    db_bank.bonds = []
    return db_bank


@app.put("/api/banks/{bank_id}", response_model=schemas.Bank)
async def update_bank(
    bank_id: int,
    bank_update: schemas.BankUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Bank).where(models.Bank.id == bank_id).options(selectinload(models.Bank.bonds))
    )
    db_bank = result.scalars().first()
    if not db_bank:
        raise HTTPException(status_code=404, detail="Bank not found")

    for key, value in bank_update.model_dump(exclude_unset=True).items():
        setattr(db_bank, key, value)

    await db.commit()
    await db.refresh(db_bank)
    bonds_result = await db.execute(
        select(models.Bond).where(models.Bond.bank_id == bank_id)
    )
    db_bank.bonds = list(bonds_result.scalars().all())
    return db_bank


@app.delete("/api/banks/{bank_id}")
async def delete_bank(bank_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Bank).where(models.Bank.id == bank_id).options(selectinload(models.Bank.bonds))
    )
    db_bank = result.scalars().first()
    if not db_bank:
        raise HTTPException(status_code=404, detail="Bank not found")

    await db.delete(db_bank)
    await db.commit()
    return {"message": "Bank deleted successfully"}


# --- Bonds CRUD ---
@app.get("/api/banks/{bank_id}/bonds", response_model=list[schemas.Bond])
async def list_bonds(bank_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Bond).where(models.Bond.bank_id == bank_id)
    )
    return result.scalars().all()


@app.post("/api/banks/{bank_id}/bonds", response_model=schemas.Bond)
async def add_bond(
    bank_id: int,
    bond: schemas.BondCreate,
    db: AsyncSession = Depends(get_db),
):
    # Verify bank exists
    bank_result = await db.execute(
        select(models.Bank).where(models.Bank.id == bank_id)
    )
    if not bank_result.scalars().first():
        raise HTTPException(status_code=404, detail="Bank not found")

    db_bond = models.Bond(**bond.model_dump(), bank_id=bank_id)
    db.add(db_bond)
    await db.commit()
    await db.refresh(db_bond)
    return db_bond


@app.get("/api/bonds/lookup/{isin}")
async def lookup_bond_endpoint(isin: str):
    data = await lookup_bond_by_isin(isin)
    return data


@app.post("/api/banks/{bank_id}/bonds/quick-add", response_model=schemas.Bond)
async def quick_add_bond_for_bank(
    bank_id: int,
    req: schemas.QuickAddBondRequest,
    db: AsyncSession = Depends(get_db),
):
    bank_result = await db.execute(
        select(models.Bank).where(models.Bank.id == bank_id)
    )
    bank = bank_result.scalars().first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")

    isin = req.isin.strip().upper()
    lookup_data = await lookup_bond_by_isin(isin)

    face_val = req.face_value if req.face_value is not None else 200000.0
    lend_r = req.lendable_ratio if req.lendable_ratio is not None else 0.80
    borrow_r = req.actual_borrow_ratio if req.actual_borrow_ratio is not None else 0.50

    db_bond = models.Bond(
        bank_id=bank_id,
        isin=isin,
        name=lookup_data.get("name") or f"債券 {isin}",
        face_value=face_val,
        lendable_ratio=lend_r,
        actual_borrow_ratio=borrow_r,
        latest_price=lookup_data.get("latest_price"),
        price_source=lookup_data.get("price_source"),
        price_source_url=lookup_data.get("price_source_url"),
        price_updated_at=datetime.datetime.utcnow() if lookup_data.get("latest_price") else None,
        currency="USD"
    )
    db.add(db_bond)
    await db.commit()
    await db.refresh(db_bond)
    return db_bond


@app.put("/api/bonds/{bond_id}", response_model=schemas.Bond)
async def update_bond(
    bond_id: int,
    bond_update: schemas.BondUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Bond).where(models.Bond.id == bond_id)
    )
    db_bond = result.scalars().first()
    if not db_bond:
        raise HTTPException(status_code=404, detail="Bond not found")

    update_data = bond_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_bond, key, value)

    # 若手動修改了報價，更新時間戳記
    if "latest_price" in update_data and update_data["latest_price"] is not None:
        db_bond.price_updated_at = datetime.datetime.utcnow()

    # 若設定了報價來源網址，自動嘗試自該網址即時抓取最新報價
    if "price_source_url" in update_data and update_data["price_source_url"]:
        try:
            live_price = await fetch_bond_price(db_bond.isin, db_bond.price_source_url)
            if live_price is not None and live_price > 0:
                db_bond.latest_price = round(float(live_price), 3)
                db_bond.price_updated_at = datetime.datetime.utcnow()
        except Exception:
            pass

    await db.commit()
    await db.refresh(db_bond)
    return db_bond


@app.delete("/api/bonds/{bond_id}")
async def delete_bond(bond_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Bond).where(models.Bond.id == bond_id)
    )
    db_bond = result.scalars().first()
    if not db_bond:
        raise HTTPException(status_code=404, detail="Bond not found")

    await db.delete(db_bond)
    await db.commit()
    return {"message": "Bond deleted successfully"}


# --- Price & Rate ---
@app.post("/api/bonds/{bond_id}/refresh-price")
async def refresh_bond_price_endpoint(
    bond_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(models.Bond).where(models.Bond.id == bond_id)
    )
    db_bond = result.scalars().first()
    if not db_bond:
        raise HTTPException(status_code=404, detail="Bond not found")

    new_price = await fetch_bond_price(db_bond.isin, db_bond.price_source_url)
    if new_price is not None and new_price > 0:
        db_bond.latest_price = round(float(new_price), 3)
        db_bond.price_updated_at = datetime.datetime.utcnow()
        await db.commit()
        return {"message": f"報價更新成功！最新報價：{new_price}", "price": new_price}

    return {
        "message": "無法自動取得最新報價，維持原價格。請確認報價來源網址，或於編輯中手動輸入。",
        "price": db_bond.latest_price,
    }



@app.post("/api/banks/{bank_id}/refresh-all")
async def refresh_all_prices(
    bank_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Bond).where(models.Bond.bank_id == bank_id)
    )
    bonds = result.scalars().all()
    if not bonds:
        return {"message": "該銀行尚無債券資料", "updated_count": 0}

    # 同步並行查詢所有債券報價 (Frankfurt API / 來源網址)
    tasks = [fetch_bond_price(b.isin, b.price_source_url) for b in bonds]
    prices = await asyncio.gather(*tasks, return_exceptions=True)

    updated_count = 0
    now = datetime.datetime.utcnow()
    for bond, price in zip(bonds, prices):
        if isinstance(price, (int, float)) and price > 0:
            bond.latest_price = round(float(price), 3)
            bond.price_updated_at = now
            updated_count += 1

    await db.commit()
    msg = f"成功更新 {updated_count} 筆債券即時報價！" if updated_count > 0 else "已連線查詢，維持目前最新報價"
    return {"message": msg, "updated_count": updated_count}


@app.get("/api/exchange-rate")
async def get_exchange_rate():
    rate = await ExchangeRateService.get_rate()
    return {"rate": rate, "currency_pair": "USD/TWD"}


@app.post("/api/exchange-rate/refresh")
async def refresh_exchange_rate():
    rate = await ExchangeRateService.get_rate(force_refresh=True)
    return {"rate": rate, "message": "匯率已刷新"}


# --- Dashboard ---
@app.get("/api/banks/{bank_id}/dashboard", response_model=schemas.DashboardData)
async def get_dashboard(bank_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Bank).where(models.Bank.id == bank_id)
    )
    bank = result.scalars().first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")

    bonds_result = await db.execute(
        select(models.Bond).where(models.Bond.bank_id == bank.id)
    )
    bonds = bonds_result.scalars().all()

    rate = await ExchangeRateService.get_rate()

    dashboard_bonds = []
    total_market_value_usd = 0.0
    total_floating_loan_usd = 0.0

    for bond in bonds:
        price = bond.latest_price or 0.0
        market_value_usd = bond.face_value * (price / 100.0)
        market_value_twd = market_value_usd * rate
        total_market_value_usd += market_value_usd

        # 單筆債券實際借用金額 (USD/TWD) = 持有面額 * 實際借用成數 (借款本金固定，不隨市價波動)
        actual_borrow = bond.actual_borrow_ratio or 0.0
        bond_borrow_usd = bond.face_value * actual_borrow
        bond_borrow_twd = bond_borrow_usd * rate
        total_floating_loan_usd += bond_borrow_usd

        dashboard_bonds.append(
            schemas.DashboardBondInfo(
                id=bond.id,
                bank_id=bond.bank_id,
                isin=bond.isin,
                name=bond.name,
                face_value=bond.face_value,
                lendable_ratio=bond.lendable_ratio,
                actual_borrow_ratio=bond.actual_borrow_ratio,
                latest_price=bond.latest_price,
                price_source_url=bond.price_source_url,
                price_source=bond.price_source,
                currency=bond.currency or "USD",
                price_updated_at=bond.price_updated_at,
                created_at=bond.created_at,
                updated_at=bond.updated_at,
                market_value_usd=round(market_value_usd, 2),
                market_value_twd=round(market_value_twd, 2),
                borrow_amount_usd=round(bond_borrow_usd, 2),
                borrow_amount_twd=round(bond_borrow_twd, 2),
            )
        )

    total_market_value_twd = total_market_value_usd * rate
    total_floating_loan_twd = total_floating_loan_usd * rate
    # Bank total_loan_amount is stored in 萬, convert to actual TWD
    total_loan_actual = (bank.total_loan_amount or 0) * 10000

    maintenance_ratio = (
        (total_market_value_twd / total_loan_actual) * 100
        if total_loan_actual > 0
        else 0
    )

    warning_status = "Safe"
    if maintenance_ratio > 0:
        if maintenance_ratio < bank.margin_call_ratio:
            warning_status = "Danger"  # 需補倉催繳
        elif maintenance_ratio < bank.warning_ratio:
            warning_status = "Warning"  # 接近補倉線

    return schemas.DashboardData(
        bank_info=bank,
        bonds=dashboard_bonds,
        total_market_value_usd=round(total_market_value_usd, 2),
        total_market_value_twd=round(total_market_value_twd, 2),
        total_floating_loan_usd=round(total_floating_loan_usd, 2),
        total_floating_loan_twd=round(total_floating_loan_twd, 2),
        total_loan_amount_twd=total_loan_actual,
        current_maintenance_ratio=round(maintenance_ratio, 2),
        warning_status=warning_status,
        exchange_rate=rate,
    )


# --- Mount static files (must be LAST, as catch-all) ---
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
