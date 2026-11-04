from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    CLIENT = "client"


class BookingStatus(str, Enum):
    PENDING = "en_attente"
    CONFIRMED = "confirmee"
    REFUSED = "refusee"
    CANCELLED = "annulee"
    COMPLETED = "terminee"


class EventType(str, Enum):
    WEDDING = "mariage"
    BIRTHDAY = "anniversaire"
    COMPANY = "entreprise"
    PRIVATE_PARTY = "fete_privee"
    OTHER = "autre"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), default=UserRole.CLIENT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bookings: Mapped[list["Booking"]] = relationship(back_populates="client")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detailed_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    magic_tricks: Mapped[str | None] = mapped_column(Text, nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bookings: Mapped[list["Booking"]] = relationship(back_populates="offer")


class SiteSetting(Base):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"))
    client_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[EventType] = mapped_column(SqlEnum(EventType))
    event_date: Mapped[date] = mapped_column(Date)
    event_time: Mapped[time] = mapped_column(Time)
    location: Mapped[str] = mapped_column(String(255))
    participants: Mapped[int] = mapped_column(Integer)
    additional_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_at_booking: Mapped[float] = mapped_column(Float)
    status: Mapped[BookingStatus] = mapped_column(SqlEnum(BookingStatus), default=BookingStatus.PENDING)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(20), default="a_payer")
    payment_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payment_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client: Mapped[User] = relationship(back_populates="bookings")
    offer: Mapped[Offer] = relationship(back_populates="bookings")

    @property
    def offer_name(self) -> str:
        return self.offer.name


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="a_signer")
    signature_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped[Booking] = relationship()
