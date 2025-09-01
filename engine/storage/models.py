from __future__ import annotations
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Numeric, Enum, Boolean, ForeignKey

class Base(DeclarativeBase): ...

class OrderStatus(PyEnum):
    open_ = "open"
    partially_filled = "partially_filled"
    closed = "closed"
    canceled = "canceled"

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(20), default="bitget")
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    side: Mapped[str] = mapped_column(Enum("buy","sell", name="side"))
    type: Mapped[str] = mapped_column(Enum("market","limit", name="otype"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), index=True, default=OrderStatus.open_)
    amount: Mapped[float] = mapped_column(Numeric(28, 12))
    price: Mapped[float | None] = mapped_column(Numeric(28, 12), nullable=True)
    filled: Mapped[float] = mapped_column(Numeric(28, 12), default=0)
    avg_price: Mapped[float | None] = mapped_column(Numeric(28, 12), nullable=True)
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False)
    client_oid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    side: Mapped[str] = mapped_column(Enum("buy","sell", name="tradeside"))
    price: Mapped[float] = mapped_column(Numeric(28, 12))
    amount: Mapped[float] = mapped_column(Numeric(28, 12))
    fee_currency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fee_cost: Mapped[float | None] = mapped_column(Numeric(28, 12), nullable=True)
    is_maker: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    exchange_trade_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True, unique=True)
    qty: Mapped[float] = mapped_column(Numeric(28, 12), default=0)
    entry_price: Mapped[float] = mapped_column(Numeric(28, 12), default=0)
    realized_pnl: Mapped[float] = mapped_column(Numeric(28, 12), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
