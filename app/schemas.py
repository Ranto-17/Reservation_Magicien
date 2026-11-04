from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import BookingStatus, EventType, UserRole


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=30)
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    # Keep legacy accounts readable even if their historical domain is not
    # accepted by EmailStr (for example, admin@magicien.local).
    email: str
    phone: str
    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OfferBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10)
    subtitle: str | None = Field(default=None, max_length=255)
    detailed_description: str | None = None
    magic_tricks: str | None = None
    conclusion: str | None = None
    price: float = Field(gt=0)
    duration_minutes: int = Field(gt=0, le=1440)
    image_url: str | None = None


class OfferRead(OfferBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool


class BookingCreate(BaseModel):
    offer_id: int
    client_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    email: EmailStr
    event_type: EventType
    event_date: date
    event_time: time
    location: str = Field(min_length=2, max_length=255)
    participants: int = Field(gt=0, le=100000)
    additional_message: str | None = Field(default=None, max_length=5000)

    @field_validator("event_date")
    @classmethod
    def date_is_not_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("La date de l'événement ne peut pas être passée")
        return value


class BookingRead(BookingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    price_at_booking: float
    status: BookingStatus
    created_at: datetime
    offer_name: str
    payment_method: str | None
    payment_reference: str | None
    payment_status: str
    payment_submitted_at: datetime | None
    payment_confirmed_at: datetime | None


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


class ContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    booking_id: int
    content: str
    status: str
    signature_name: str | None
    signed_at: datetime | None
    created_at: datetime


class ContractSignature(BaseModel):
    signature_name: str = Field(min_length=2, max_length=120)


class PaymentSubmission(BaseModel):
    payment_method: str = Field(pattern="^(mvola|orange_money|airtel_money)$")
    payment_reference: str = Field(min_length=4, max_length=120)
